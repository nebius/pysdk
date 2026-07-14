#!/usr/bin/env python3
"""Generate the direct API into a staging tree and promote it atomically."""

from __future__ import annotations

import argparse
import ast
import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE_ROOT = ROOT / "build" / "generated" / "src"
STAGED_API = STAGE_ROOT / "nebius" / "api" / "nebius"
TARGET_API = ROOT / "src" / "nebius" / "api" / "nebius"
BACKUP_API = ROOT / "build" / "generated-api-backup"
LOCK_FILE = ROOT / "build" / ".generate-api.lock"
IGNORED_TREE_NAMES = {"__pycache__"}


def same_tree(left: Path, right: Path) -> bool:
    """Return whether two directory trees contain identical files."""
    if not left.is_dir() or not right.is_dir():
        return False
    comparison = filecmp.dircmp(left, right, ignore=list(IGNORED_TREE_NAMES))
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False
    if any(
        (left / name).read_bytes() != (right / name).read_bytes()
        for name in comparison.common_files
    ):
        return False
    return all(same_tree(left / name, right / name) for name in comparison.common_dirs)


def validate_python_tree(root: Path) -> None:
    """Parse every generated Python file without creating cache files."""
    for source in root.rglob("*.py"):
        ast.parse(source.read_text(), filename=str(source))


def smoke_test(extra_path: Path | None = None) -> None:
    """Import, construct, encode, and decode a representative generated type."""
    paths = [ROOT / "src"]
    if extra_path is not None:
        paths.insert(0, extra_path)
    code = f"""
import sys
wanted = {[str(path) for path in paths]!r}
sys.path = wanted + [
    path for path in sys.path
    if not (path.endswith('/pysdk/src') and path not in wanted)
]
from nebius.api.nebius.compute.v1 import DiskSpec
message = DiskSpec(size_gibibytes=8, type=DiskSpec.DiskType.NETWORK_SSD)
wire = message.SerializeToString(deterministic=True)
decoded = DiskSpec.FromString(wire)
assert decoded.size_gibibytes == 8
assert decoded.type is DiskSpec.DiskType.NETWORK_SSD
assert not hasattr(message, '__pb2_message__')
"""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, check=True)


def generate() -> None:
    """Run the local Buf plugin into the configured staging directory."""
    shutil.rmtree(STAGE_ROOT.parent, ignore_errors=True)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [str(Path(sys.executable).parent), env.get("PATH", "")]
    )
    subprocess.run(
        [
            "buf",
            "generate",
            "nebius-api",
            "--include-imports",
            "--timeout",
            "0",
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    if not STAGED_API.is_dir():
        raise RuntimeError(f"Generator did not create {STAGED_API}")
    validate_python_tree(STAGED_API)
    smoke_test(STAGE_ROOT)


def recover_interrupted_promotion(
    target: Path = TARGET_API,
    backup: Path = BACKUP_API,
) -> bool:
    """Restore the last live tree after an interrupted directory swap."""
    if target.exists():
        if backup.exists():
            shutil.rmtree(backup)
        return False
    if not backup.exists():
        raise RuntimeError(f"Generated API tree is missing: {target}")
    backup.rename(target)
    return True


def promote() -> None:
    """Promote the staged API and restore the previous tree on any failure."""
    if BACKUP_API.exists():
        raise RuntimeError(f"Unexpected generated API backup: {BACKUP_API}")
    TARGET_API.rename(BACKUP_API)
    try:
        STAGED_API.rename(TARGET_API)
        smoke_test()
    except BaseException:
        shutil.rmtree(TARGET_API, ignore_errors=True)
        BACKUP_API.rename(TARGET_API)
        raise
    shutil.rmtree(BACKUP_API)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(f"Generation is already running: {LOCK_FILE}") from error
    try:
        os.close(lock_fd)
        recover_interrupted_promotion()
        generate()
        unchanged = same_tree(STAGED_API, TARGET_API)
        if args.check:
            if not unchanged:
                print("Generated API is out of date.", file=sys.stderr)
                return 1
            print("Generated API is up to date.")
            return 0
        if args.dry_run:
            print(
                "Generated API is up to date."
                if unchanged
                else "Generated API would change."
            )
            return 0
        if unchanged:
            print("Generated API is unchanged; nothing to promote.")
            return 0
        promote()
        print("Generated API promoted successfully.")
        return 0
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
