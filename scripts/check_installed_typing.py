"""Check public SDK typing from the installed wheel, not the source tree."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from importlib import import_module
from importlib.metadata import distribution
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory

VALID_CONSUMER = """\
from nebius.aio.request import Request
from nebius.api.nebius.compute.v1 import (
    Disk,
    DiskServiceClient,
    DiskSpec,
    GetDiskRequest,
)


def use_sdk(
    client: DiskServiceClient,
) -> tuple[int | None, Request[GetDiskRequest, Disk]]:
    spec = DiskSpec(size_gibibytes=10)
    disk = Disk(spec=spec)
    size: int | None = disk.spec.size_gibibytes
    request: Request[GetDiskRequest, Disk] = client.get(
        GetDiskRequest(id="disk-id"), timeout=5.0
    )
    return size, request
"""


INVALID_CONSUMER = """\
from nebius.api.nebius.compute.v1 import (
    DiskServiceClient,
    DiskSpec,
    TotallyMissing,
)


def misuse_sdk(client: DiskServiceClient) -> None:
    DiskSpec(size_gibibytes="ten")
    client.get(DiskSpec())
"""


def _run(module: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    fixture = Path(arguments[-1])
    environment = environ.copy()
    for name in ("MYPYPATH", "PYTHONPATH", "PYRIGHT_PYTHONPATH"):
        environment.pop(name, None)
    return subprocess.run(  # noqa: S603 - checker modules and arguments are fixed
        [sys.executable, "-m", module, *arguments],
        check=False,
        capture_output=True,
        text=True,
        cwd=fixture.parent,
        env=environment,
    )


def _check_wheel_contents() -> None:
    installed_distribution = distribution("nebius")
    runtime_version = import_module("nebius.base.version").version
    if runtime_version != installed_distribution.version:
        raise RuntimeError(
            "SDK runtime version does not match package metadata: "
            f"{runtime_version!r} != {installed_distribution.version!r}"
        )

    files = installed_distribution.files
    if files is None:
        raise RuntimeError("the installed nebius distribution has no file manifest")
    paths = {Path(str(file)) for file in files}
    if Path("nebius/py.typed") not in paths:
        raise RuntimeError("the installed wheel does not contain nebius/py.typed")

    for namespace in ("nebius.api", "nebius.api.google"):
        spec = importlib.util.find_spec(namespace)
        if (
            spec is None
            or spec.origin is not None
            or not spec.submodule_search_locations
        ):
            raise RuntimeError(f"{namespace} is not an installed PEP 420 namespace")

    generated_modules: list[str] = []
    for path in sorted(paths):
        if path.suffix != ".py" or path.parts[:2] != ("nebius", "api"):
            continue
        if any(part.endswith(("_pb2.py", "_pb2_grpc.py")) for part in path.parts):
            raise RuntimeError(f"legacy generated module shipped in wheel: {path}")
        parts = path.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        generated_modules.append(".".join(parts))
    if not generated_modules:
        raise RuntimeError("the installed wheel contains no generated API modules")
    for module in generated_modules:
        import_module(module)


def _assert_success(result: subprocess.CompletedProcess[str], checker: str) -> None:
    if result.returncode != 0:
        output = result.stdout + result.stderr
        raise RuntimeError(f"{checker} rejected the valid consumer:\n{output}")


def _assert_expected_failure(
    result: subprocess.CompletedProcess[str], checker: str
) -> None:
    output = result.stdout + result.stderr
    if result.returncode == 0:
        raise RuntimeError(f"{checker} accepted the invalid consumer")
    for expected in ("size_gibibytes", "DiskSpec", "TotallyMissing"):
        if expected not in output:
            raise RuntimeError(
                f"{checker} did not report the expected {expected!r} "
                f"diagnostic:\n{output}"
            )


def main() -> None:
    package = importlib.util.find_spec("nebius")
    if package is None or package.origin is None:
        raise RuntimeError("the nebius wheel is not installed")
    source_tree = Path(__file__).resolve().parents[1] / "src"
    if Path(package.origin).resolve().is_relative_to(source_tree):
        raise RuntimeError("typing check resolved nebius from the source tree")
    _check_wheel_contents()

    with TemporaryDirectory(prefix="nebius-wheel-typing-") as temporary:
        directory = Path(temporary)
        valid = directory / "valid_consumer.py"
        invalid = directory / "invalid_consumer.py"
        valid.write_text(VALID_CONSUMER)
        invalid.write_text(INVALID_CONSUMER)
        pyright_config = directory / "pyrightconfig.json"
        site_packages = distribution("nebius").locate_file("").resolve()
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        pyright_config.write_text(
            json.dumps(
                {
                    "extraPaths": [str(site_packages)],
                    "pythonVersion": python_version,
                    "typeCheckingMode": "strict",
                }
            )
        )

        mypy_arguments = ("--strict", "--no-incremental")
        _assert_success(_run("mypy", *mypy_arguments, str(valid)), "mypy")
        _assert_expected_failure(_run("mypy", *mypy_arguments, str(invalid)), "mypy")

        pyright_arguments = ("--project", str(pyright_config))
        _assert_success(_run("pyright", *pyright_arguments, str(valid)), "pyright")
        _assert_expected_failure(
            _run("pyright", *pyright_arguments, str(invalid)), "pyright"
        )


if __name__ == "__main__":
    main()
