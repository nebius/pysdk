"""Provider-free Buf plugin that captures one exact generation request."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .bootstrap import CodeGeneratorResponse

MANIFEST_ENV = "NEBIUS_GENERATOR_MANIFEST"


def main() -> None:
    manifest_value = os.environ.get(MANIFEST_ENV)
    if not manifest_value:
        raise RuntimeError(f"{MANIFEST_ENV} is required")
    manifest = Path(manifest_value)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_name(manifest.name + ".tmp")
    with temporary.open("wb") as output:
        while chunk := sys.stdin.buffer.read(1024 * 1024):
            output.write(chunk)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(manifest)
    response = CodeGeneratorResponse(
        supported_features=int(CodeGeneratorResponse.Feature.FEATURE_PROTO3_OPTIONAL)
    )
    sys.stdout.buffer.write(response.SerializeToString(deterministic=True))


if __name__ == "__main__":
    main()
