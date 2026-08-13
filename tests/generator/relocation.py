"""Helpers for exercising generated APIs under relocated SDK namespaces."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def materialize(root: Path, namespace: str, response: Any) -> None:
    """Write generated files and a relocated copy of the wheel runtime."""
    runtime = root.joinpath(*namespace.split("."))
    shutil.copytree(
        Path(__file__).parents[2] / "src" / "nebius",
        runtime,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache"),
    )
    for output in response.file:
        path = root / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)
