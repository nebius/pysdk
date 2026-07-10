from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

from google.protobuf import descriptor_pb2
from google.protobuf.compiler import plugin_pb2


def field(
    message: descriptor_pb2.DescriptorProto,
    name: str,
    number: int,
    type_: int,
    *,
    type_name: str = "",
    label: int = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
    oneof_index: int | None = None,
    proto3_optional: bool = False,
) -> None:
    value = message.field.add(
        name=name,
        number=number,
        type=type_,
        label=label,
    )
    if type_name:
        value.type_name = type_name
    if proto3_optional:
        value.proto3_optional = True
    if oneof_index is not None:
        value.oneof_index = oneof_index


def request() -> plugin_pb2.CodeGeneratorRequest:
    common = descriptor_pb2.FileDescriptorProto(
        name="acme/common.proto",
        package="acme.common",
        syntax="proto3",
    )
    shared = common.message_type.add(name="Shared")
    field(shared, "value", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)

    widget_file = descriptor_pb2.FileDescriptorProto(
        name="acme/widget.proto",
        package="acme.widget",
        syntax="proto3",
        dependency=[common.name],
    )
    widget = widget_file.message_type.add(name="Widget")
    widget.oneof_decl.add(name="choice")
    widget.oneof_decl.add(name="_enabled")
    field(widget, "id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT64)
    field(
        widget,
        "name",
        2,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        oneof_index=0,
    )
    field(
        widget,
        "count",
        3,
        descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
        oneof_index=0,
    )
    field(
        widget,
        "shared",
        4,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".acme.common.Shared",
    )
    field(
        widget,
        "tags",
        5,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    entry = widget.nested_type.add(name="AttributesEntry")
    entry.options.map_entry = True
    field(entry, "key", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    field(entry, "value", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    field(
        widget,
        "attributes",
        6,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".acme.widget.Widget.AttributesEntry",
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    field(
        widget,
        "enabled",
        7,
        descriptor_pb2.FieldDescriptorProto.TYPE_BOOL,
        oneof_index=1,
        proto3_optional=True,
    )
    return plugin_pb2.CodeGeneratorRequest(
        proto_file=[common, widget_file],
        file_to_generate=[common.name, widget_file.name],
    )


def generate(root: Path, namespace: str) -> None:
    generator_request = request()
    generator_request.parameter = ",".join(
        [
            f"import_substitution=acme={namespace}.acme",
            f"export_substitution=acme={namespace}.acme",
        ]
    )
    completed = subprocess.run(
        [sys.executable, "-m", "nebius_generator.main"],
        input=generator_request.SerializeToString(),
        capture_output=True,
        check=True,
    )
    response = plugin_pb2.CodeGeneratorResponse.FromString(completed.stdout)
    assert not response.error
    for generated in response.file:
        path = root / generated.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generated.content)


def test_direct_classes_coexist_in_two_namespaces(tmp_path: Path) -> None:
    generate(tmp_path, "ns_one")
    generate(tmp_path, "ns_two")
    generated_source = "\n".join(path.read_text() for path in tmp_path.rglob("*.py"))
    assert "__PB2_CLASS__" not in generated_source
    assert "__pb2_message__" not in generated_source
    assert "import ns_one.acme" not in generated_source
    assert "import ns_two.acme" not in generated_source

    sys.path.insert(0, str(tmp_path))
    try:
        one_common = importlib.import_module("ns_one.acme.common")
        one_widget = importlib.import_module("ns_one.acme.widget")
        two_widget = importlib.import_module("ns_two.acme.widget")

        original = one_widget.Widget(
            id=2**62,
            name="first",
            shared=one_common.Shared(value="cross-namespace"),
            tags=["a", "b"],
            attributes={"region": "eu"},
            enabled=False,
        )
        original.count = 0
        wire = original.SerializeToString(deterministic=True)
        decoded = two_widget.Widget.FromString(wire + b"\x98\x06\x07")

        assert decoded.id == 2**62
        assert decoded.choice is not None
        assert decoded.choice.field == "count"
        assert decoded.count == 0
        assert decoded.shared.value == "cross-namespace"
        assert list(decoded.tags) == ["a", "b"]
        assert dict(decoded.attributes) == {"region": "eu"}
        assert decoded.enabled is False
        assert b"\x98\x06\x07" in decoded.SerializeToString(deterministic=True)
        assert type(original) is not type(decoded)
    finally:
        sys.path.remove(str(tmp_path))
