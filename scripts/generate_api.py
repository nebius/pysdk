#!/usr/bin/env python3
"""Stage, validate, compare, and atomically publish the generated API."""

from __future__ import annotations

import argparse
import ast
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import portalocker

ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = ROOT / "nebius-api"
STAGING_PARENT = ROOT / "build" / "generated-runs"
TARGET_API = ROOT / "src" / "nebius" / "api"
BACKUP_API = ROOT / "build" / "generated-api-backup"
RETIRED_API = ROOT / "build" / "generated-api-retired"
PROMOTION_MARKER = ROOT / "build" / ".generated-api-promotion"
LOCK = ROOT / "build" / ".generate-api.lock"


def same_tree(left: Path, right: Path) -> bool:
    if not left.is_dir() or not right.is_dir():
        return False
    comparison = filecmp.dircmp(left, right, ignore=["__pycache__"])
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False
    if any(
        (left / name).read_bytes() != (right / name).read_bytes()
        for name in comparison.common_files
    ):
        return False
    return all(same_tree(left / name, right / name) for name in comparison.common_dirs)


def capture_template(
    partition: str,
    jobs: int,
    output: Path,
    path: Path,
    cache_dir: Path | None = None,
) -> None:
    plugin = json.dumps([sys.executable, "-m", "nebius_generator.capture"])
    lines = [
        "version: v2",
        "plugins:",
        f"  - local: {plugin}",
        f"    out: {output}",
        "    opt:",
        "      - package_prefix=nebius.api",
        "      - runtime_package=nebius",
        f"      - partition={partition}",
        f"      - jobs={jobs}",
    ]
    if cache_dir is not None:
        lines.append(f"      - cache_dir={cache_dir}")
    lines.extend(("    strategy: all", ""))
    path.write_text("\n".join(lines))


def validate(root: Path) -> None:
    sources = sorted(root.rglob("*.py"))
    if not sources:
        raise RuntimeError("generator produced no Python files")
    for source in sources:
        ast.parse(source.read_text(), filename=str(source))
    forbidden = [
        path for path in sources if path.name.endswith(("_pb2.py", "_pb2_grpc.py"))
    ]
    if forbidden:
        raise RuntimeError(f"provider-generated files remain: {forbidden[0]}")
    modules = tuple(
        ".".join(("nebius", "api", *path.relative_to(root).parent.parts))
        for path in sources
        if path.name == "__init__.py"
    )
    code = f"""
import importlib
for module in {modules!r}:
    importlib.import_module(module)
from nebius.api.nebius.compute.v1 import DiskSpec
from nebius.api.google.protobuf import Timestamp
message = DiskSpec(type=DiskSpec.DiskType.NETWORK_SSD)
assert DiskSpec.FromString(message.SerializeToString()).type == message.type
assert Timestamp().SerializeToString() == b''
"""
    with tempfile.TemporaryDirectory(prefix="nebius-api-import-") as temporary:
        merged = Path(temporary) / "src"
        runtime = merged / "nebius"
        shutil.copytree(
            ROOT / "src" / "nebius",
            runtime,
            ignore=shutil.ignore_patterns("api", "__pycache__", "*.pyc"),
        )
        shutil.copytree(root, runtime / "api")
        isolated_code = f"import sys; sys.path.insert(0, {str(merged)!r})\n" + code
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment.pop("PYTHONPATH", None)
        subprocess.run(  # noqa: S603 - current interpreter and constant smoke code
            [sys.executable, "-I", "-c", isolated_code],
            cwd=temporary,
            env=environment,
            check=True,
        )


def generate(
    partition: str,
    jobs: int,
    run_root: Path,
    cache_dir: Path | None = None,
) -> Path:
    capture_output = run_root / "capture-output"
    manifest = run_root / "request.bin"
    staged_source = run_root / "src"
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        template_path = Path(handle.name)
    try:
        capture_template(partition, jobs, capture_output, template_path, cache_dir)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(ROOT / "src")))
        environment["NEBIUS_GENERATOR_MANIFEST"] = str(manifest)
        buf = shutil.which("buf")
        if buf is None:
            raise RuntimeError("buf is not installed or is missing from PATH")
        subprocess.run(  # noqa: S603 - resolved trusted build tool
            [
                buf,
                "generate",
                str(PROTO_ROOT),
                "--timeout",
                "0",
                "--template",
                str(template_path),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    finally:
        template_path.unlink(missing_ok=True)
    if not manifest.is_file():
        raise RuntimeError(f"capture plugin did not produce {manifest}")
    subprocess.run(  # noqa: S603 - current interpreter and repository module
        [
            sys.executable,
            "-m",
            "nebius_generator.coordinator",
            str(manifest),
            str(staged_source),
            "--include-generator-protocol",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    staged_api = staged_source / "nebius" / "api"
    validate(staged_api)
    return staged_api


def recover() -> None:
    if PROMOTION_MARKER.exists():
        previous = (
            BACKUP_API
            if BACKUP_API.exists()
            else RETIRED_API if RETIRED_API.exists() else None
        )
        if previous is not None:
            shutil.rmtree(TARGET_API, ignore_errors=True)
            previous.rename(TARGET_API)
        elif not TARGET_API.exists():
            raise RuntimeError("interrupted generation has no live or backup API tree")
        PROMOTION_MARKER.unlink()
    shutil.rmtree(RETIRED_API, ignore_errors=True)
    if BACKUP_API.exists():
        raise RuntimeError(f"generation backup exists without marker: {BACKUP_API}")
    if not TARGET_API.exists():
        raise RuntimeError(f"generated API tree is missing: {TARGET_API}")


def promote(
    staged_api: Path,
    validate_promoted: Callable[[Path], None] | None = None,
) -> None:
    if BACKUP_API.exists():
        raise RuntimeError(f"unexpected generation backup: {BACKUP_API}")
    if RETIRED_API.exists():
        raise RuntimeError(f"unexpected retired generation tree: {RETIRED_API}")
    PROMOTION_MARKER.write_text("promotion in progress\n")
    live_moved = False
    try:
        TARGET_API.rename(BACKUP_API)
        live_moved = True
        staged_api.rename(TARGET_API)
        (validate_promoted or validate)(TARGET_API)
        BACKUP_API.rename(RETIRED_API)
        PROMOTION_MARKER.unlink()
    except BaseException:
        previous = (
            BACKUP_API
            if BACKUP_API.exists()
            else RETIRED_API if RETIRED_API.exists() else None
        )
        if not live_moved and previous is None:
            PROMOTION_MARKER.unlink()
            raise
        shutil.rmtree(TARGET_API, ignore_errors=True)
        if previous is not None:
            try:
                previous.rename(TARGET_API)
            except BaseException:
                raise
            else:
                PROMOTION_MARKER.unlink()
        raise
    shutil.rmtree(RETIRED_API, ignore_errors=True)


def validate_cache_path(cache_dir: Path | None) -> None:
    if cache_dir is None:
        return
    cache = cache_dir.expanduser().resolve()
    protected = (TARGET_API, BACKUP_API, RETIRED_API, STAGING_PARENT)
    if any(
        cache == path.resolve()
        or cache.is_relative_to(path.resolve())
        or path.resolve().is_relative_to(cache)
        for path in protected
    ):
        raise ValueError(f"cache directory overlaps generated API paths: {cache}")


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--verify-partitions", action="store_true")
    mode.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--partition", choices=("all", "package", "directory"), default="all"
    )
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    validate_cache_path(args.cache_dir)
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with portalocker.Lock(LOCK, timeout=0):
        recovery_pending = any(
            path.exists() for path in (PROMOTION_MARKER, BACKUP_API, RETIRED_API)
        )
        if args.check or args.verify_partitions or args.validate_only:
            if recovery_pending:
                raise RuntimeError(
                    "generated API recovery is required; run update mode first"
                )
        else:
            recover()
        STAGING_PARENT.mkdir(parents=True, exist_ok=True)
        if args.verify_partitions:
            run_roots = [
                Path(tempfile.mkdtemp(prefix=f"{partition}-", dir=STAGING_PARENT))
                for partition in ("all", "package", "directory")
            ]
            try:
                outputs = [
                    generate(partition, args.jobs, run_root, args.cache_dir)
                    for partition, run_root in zip(
                        ("all", "package", "directory"), run_roots, strict=True
                    )
                ]
                if not all(same_tree(outputs[0], output) for output in outputs[1:]):
                    print("Generator partition outputs differ.", file=sys.stderr)
                    return 1
                return 0
            finally:
                for run_root in run_roots:
                    shutil.rmtree(run_root, ignore_errors=True)
        run_root = Path(tempfile.mkdtemp(prefix="run-", dir=STAGING_PARENT))
        verification_root: Path | None = None
        try:
            staged_api = generate(args.partition, args.jobs, run_root, args.cache_dir)
            if args.validate_only:
                return 0
            unchanged = same_tree(staged_api, TARGET_API)
            if args.check:
                if not unchanged:
                    print("Generated API is out of date.", file=sys.stderr)
                    return 1
                return 0
            verification_root = Path(
                tempfile.mkdtemp(prefix="verify-promoted-", dir=STAGING_PARENT)
            )
            promoted_run_root = verification_root

            def validate_promoted(live: Path) -> None:
                regenerated = generate(
                    args.partition,
                    args.jobs,
                    promoted_run_root,
                    args.cache_dir,
                )
                if not same_tree(live, regenerated):
                    raise RuntimeError(
                        "regenerated API is not a byte-identical fixed point"
                    )

            promote(staged_api, validate_promoted)
            return 0
        finally:
            shutil.rmtree(run_root, ignore_errors=True)
            if verification_root is not None:
                shutil.rmtree(verification_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
