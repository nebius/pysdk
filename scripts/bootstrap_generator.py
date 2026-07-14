#!/usr/bin/env python3
"""Safely refresh the generator's frozen annotation descriptors."""

from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from google.protobuf.descriptor_pb2 import DescriptorProto, FileDescriptorProto

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PROTO = ROOT / "nebius-api" / "nebius" / "annotations.proto"
TARGET = ROOT / "nebius_generator" / "_bootstrap" / "annotations_pb2.py"
LOCK_FILE = ROOT / "build" / ".bootstrap-generator.lock"
PUBLIC_MODULE = "nebius.annotations_pb2"
FROZEN_MODULE = "nebius_generator._bootstrap.annotations_pb2"


def build_candidate(directory: Path) -> Path:
    """Compile the bootstrap proto locally and return its patched module."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"--proto_path={ROOT / 'nebius-api'}",
            f"--python_out={directory}",
            str(SOURCE_PROTO.relative_to(ROOT / "nebius-api")),
        ],
        cwd=ROOT,
        check=True,
    )
    generated = directory / "nebius" / "annotations_pb2.py"
    content = generated.read_text().replace(PUBLIC_MODULE, FROZEN_MODULE)
    candidate = directory / "annotations_pb2.py"
    candidate.write_text(content)
    return candidate


def validate_candidate(candidate: Path) -> None:
    """Import the candidate alone and guard against accidental descriptor shrink."""
    code = f"""
import importlib.util
spec = importlib.util.spec_from_file_location({FROZEN_MODULE!r}, {str(candidate)!r})
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
required = {{
    'field_behavior', 'method_behavior', 'api_service_name', 'sensitive',
    'credentials', 'MessagePySDKSettings', 'MethodPySDKSettings',
}}
assert not (required - set(vars(module)))
assert len(module.DESCRIPTOR.extensions_by_name) >= 20
"""
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)


def descriptor_bytes(module: Path) -> bytes:
    """Extract the serialized file descriptor from a generated Python module."""
    tree = ast.parse(module.read_text(), filename=str(module))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "AddSerializedFile"
            and node.args
        ):
            value = ast.literal_eval(node.args[0])
            if isinstance(value, bytes):
                return value
    raise ValueError(f"No serialized descriptor found in {module}")


def semantic_descriptor_bytes(module: Path) -> bytes:
    """Normalize protoc-version-only descriptor representation differences."""
    descriptor = FileDescriptorProto.FromString(descriptor_bytes(module))

    def normalize_message(message: DescriptorProto) -> None:
        for value in message.field:
            value.ClearField("json_name")
        for value in message.extension:
            value.ClearField("json_name")
        for nested in message.nested_type:
            normalize_message(nested)

    for message in descriptor.message_type:
        normalize_message(message)
    for extension in descriptor.extension:
        extension.ClearField("json_name")
    return descriptor.SerializeToString(deterministic=True)


def run_generator_tests(candidate: Path, directory: Path) -> None:
    """Run the separate generator suite against a staged package copy."""
    staged_package = directory / "nebius_generator"
    shutil.copytree(ROOT / "nebius_generator", staged_package)
    shutil.copy2(candidate, staged_package / "_bootstrap" / "annotations_pb2.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(directory), str(ROOT), str(ROOT / "src"), env.get("PYTHONPATH", "")]
    )
    test_code = f"""
import sys
from pathlib import Path
wanted = {str(ROOT / 'src')!r}
sys.path = [
    path for path in sys.path
    if not (path.endswith('/pysdk/src') and path != wanted)
]
import nebius_generator
staged = Path({str(staged_package)!r}).resolve()
loaded = Path(nebius_generator.__file__).resolve()
assert loaded.is_relative_to(staged), (loaded, staged, sys.path)
import pytest
raise SystemExit(pytest.main(['-q', {str(ROOT / 'tests' / 'generator')!r}]))
"""
    subprocess.run(
        [sys.executable, "-c", test_code],
        cwd=directory,
        env=env,
        check=True,
    )


def promote_candidate(
    candidate: Path,
    target: Path = TARGET,
    validator: Callable[[Path], None] = validate_candidate,
) -> bool:
    """Validate and atomically promote a changed candidate.

    Returns ``True`` when the target changed.  A validation failure occurs
    before mutation, so the live bootstrap file remains byte-for-byte intact.
    """
    validator(candidate)
    if target.exists() and candidate.read_bytes() == target.read_bytes():
        return False
    temporary = target.with_suffix(".py.new")
    shutil.copy2(candidate, temporary)
    os.replace(temporary, target)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(f"Bootstrap is already running: {LOCK_FILE}") from error
    try:
        os.close(lock_fd)
        with tempfile.TemporaryDirectory(
            prefix="nebius-generator-bootstrap-",
            dir=ROOT / "build",
        ) as temp:
            directory = Path(temp)
            candidate = build_candidate(directory)
            validate_candidate(candidate)
            if semantic_descriptor_bytes(candidate) == semantic_descriptor_bytes(
                TARGET
            ):
                print("Generator bootstrap is unchanged.")
                return 0
            run_generator_tests(candidate, directory)
            if args.dry_run:
                print("Generator bootstrap would change; staged tests passed.")
                return 0
            changed = promote_candidate(candidate)
            print(
                "Generator bootstrap promoted."
                if changed
                else "Generator bootstrap is unchanged."
            )
            return 0
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
