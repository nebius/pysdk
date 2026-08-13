"""The installed package is self-contained under one relocatable namespace."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE_PACKAGE = Path(__file__).parents[1] / "src" / "nebius"


def test_shipped_sources_have_no_absolute_self_imports() -> None:
    for path in SOURCE_PACKAGE.rglob("*.py"):
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert (
                    node.level or not node.module or not (node.module == "nebius" or node.module.startswith("nebius."))
                ), f"absolute self-import in {path}:{node.lineno}"
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name == "nebius" or alias.name.startswith("nebius.") for alias in node.names
                ), f"absolute self-import in {path}:{node.lineno}"


def test_representative_package_imports_after_relocation(tmp_path: Path) -> None:
    destination = tmp_path / "some" / "other" / "namespace"
    shutil.copytree(
        SOURCE_PACKAGE,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache"),
    )
    code = f"""
import sys
import importlib
sys.path.insert(0, {str(tmp_path)!r})
from some.other.namespace.api.google.protobuf import Timestamp
from some.other.namespace.api.nebius.compute.v1 import DiskSpec
from some.other.namespace.sdk import SDK
for module in (
    'some.other.namespace.aio.token.federation_bearer.auth',
    'some.other.namespace.aio.token.file_cache.async_renewable_bearer',
    'some.other.namespace.base.protos.pb_classes',
    'some.other.namespace.base.service_account.federated_credentials',
    'some.other.namespace.examples.basic',
):
    importlib.import_module(module)
assert Timestamp().SerializeToString() == b''
value = DiskSpec(type=DiskSpec.DiskType.NETWORK_SSD)
assert DiskSpec.FromString(value.SerializeToString()).type == value.type
assert SDK.__module__ == 'some.other.namespace.sdk'
assert 'nebius' not in sys.modules
"""
    subprocess.run([sys.executable, "-I", "-c", code], check=True)
