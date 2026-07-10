from __future__ import annotations

import importlib.resources
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).with_name("typing")


def run_mypy(path: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    config = tmp_path / "mypy.ini"
    config.write_text(
        "[mypy]\n"
        "strict = True\n"
        "follow_imports = silent\n"
        f"cache_dir = {tmp_path / 'cache'}\n"
    )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(config),
            str(path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_installed_package_exposes_generated_types(tmp_path: Path) -> None:
    marker = importlib.resources.files("nebius").joinpath("py.typed")
    assert marker.is_file()

    result = run_mypy(FIXTURES / "valid.py", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_types_reject_wrong_field_values(tmp_path: Path) -> None:
    result = run_mypy(FIXTURES / "invalid.py", tmp_path)
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert (
        'Argument "size_gibibytes" to "DiskSpec" has incompatible type "str"' in output
    )
    assert 'expected "int' in output
