"""Generator namespace prefix contract."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from google.protobuf import descriptor_pb2
from google.protobuf.compiler import plugin_pb2

from nebius_generator.errors import GeneratorError
from nebius_generator.main import generate
from nebius_generator.model import Options
from tests.generator.relocation import materialize

RUNTIME_PREFIX = "some.other.namespace"
DESTINATION_PREFIX = f"{RUNTIME_PREFIX}.generated.api"


def _assert_no_absolute_namespace_imports(response: plugin_pb2.CodeGeneratorResponse) -> None:
    for output in response.file:
        if not output.name.endswith(".py"):
            continue
        for node in ast.walk(ast.parse(output.content, filename=output.name)):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.level or not (
                    node.module == RUNTIME_PREFIX or node.module.startswith(RUNTIME_PREFIX + ".")
                ), f"absolute namespace import in {output.name}:{node.lineno}"
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name == RUNTIME_PREFIX or alias.name.startswith(RUNTIME_PREFIX + ".") for alias in node.names
                ), f"absolute namespace import in {output.name}:{node.lineno}"


def test_prefix_defaults_and_relocation() -> None:
    defaults = Options.parse("")
    assert defaults.destination_prefix == "nebius.api"
    assert defaults.runtime_prefix == "nebius"

    relocated = Options.parse(
        "destination_prefix=some.other.namespace.api,runtime_prefix=some.other.namespace",
    )
    assert relocated.destination_prefix == "some.other.namespace.api"
    assert relocated.runtime_prefix == "some.other.namespace"


@pytest.mark.parametrize("name", ("package_prefix", "runtime_package", "namespace"))
def test_old_or_ambiguous_prefix_options_are_rejected(name: str) -> None:
    with pytest.raises(GeneratorError, match="unknown generator parameter"):
        Options.parse(f"{name}=legacy")


@pytest.mark.parametrize(
    "parameter",
    (
        "destination_prefix=generated.api,runtime_prefix=runtime",
        "destination_prefix=runtime,runtime_prefix=runtime",
    ),
)
def test_destination_must_be_below_the_runtime_namespace(parameter: str) -> None:
    with pytest.raises(GeneratorError, match="destination_prefix must be below runtime_prefix"):
        Options.parse(parameter)


def test_deep_prefixes_generate_an_importable_tree(tmp_path: Path) -> None:
    options = descriptor_pb2.FileDescriptorProto(
        name="hidden/options.proto",
        package="hidden.options",
        syntax="proto3",
    )
    unpackaged = descriptor_pb2.FileDescriptorProto(
        name="loose.proto",
        syntax="proto3",
    )
    unpackaged.message_type.add(name="Loose")
    file = descriptor_pb2.FileDescriptorProto(
        name="acme/widget.proto",
        package="acme.widget",
        syntax="proto3",
    )
    file.dependency.extend((options.name, unpackaged.name))
    widget = file.message_type.add(name="Widget")
    widget.field.add(
        name="loose",
        number=1,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".Loose",
    )
    request = plugin_pb2.CodeGeneratorRequest(
        proto_file=[options, unpackaged, file],
        file_to_generate=[unpackaged.name, file.name],
        parameter=f"destination_prefix={DESTINATION_PREFIX},runtime_prefix={RUNTIME_PREFIX}",
    )

    response = generate(request)
    assert not response.error
    _assert_no_absolute_namespace_imports(response)
    assert any(output.name == "some/other/namespace/generated/api/_registry_fragment.py" for output in response.file)
    assert any(output.name.startswith("some/other/namespace/generated/api/_unpackaged/") for output in response.file)
    materialize(tmp_path, RUNTIME_PREFIX, response)
    code = f"""
import sys
sys.path.insert(0, {str(tmp_path)!r})
from some.other.namespace.generated.api._registry import REGISTRY
from some.other.namespace.generated.api._unpackaged import Loose
from some.other.namespace.generated.api.acme.widget import Widget
assert Widget.__module__ == 'some.other.namespace.generated.api.acme.widget'
assert REGISTRY.message_class('acme.widget.Widget') is Widget
assert REGISTRY.message_class('Loose') is Loose
assert isinstance(Widget(loose=Loose()).loose, Loose)
assert 'nebius' not in sys.modules
"""
    subprocess.run([sys.executable, "-I", "-c", code], check=True)
