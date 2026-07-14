"""Buf/protoc plugin entry point for direct Python SDK generation."""

from __future__ import annotations

import sys

from .bootstrap import (
    CodeGeneratorResponse,
    coerce_request,
    normalize_request,
    parse_request,
)
from .emitter import emit
from .errors import GeneratorError
from .model import Graph, Options


def generate(request: object) -> CodeGeneratorResponse:
    """Generate a deterministic response, reporting schema errors in-band."""
    response = CodeGeneratorResponse(
        supported_features=int(CodeGeneratorResponse.Feature.FEATURE_PROTO3_OPTIONAL)
    )
    try:
        request = normalize_request(coerce_request(request))
        graph = Graph(request, Options.parse(request.parameter))
        response.file.extend(emit(graph))
    except (GeneratorError, KeyError, ValueError) as error:
        response.error = str(error)
    return response


def main() -> None:
    request = parse_request(sys.stdin.buffer.read())
    sys.stdout.buffer.write(generate(request).SerializeToString(deterministic=True))


if __name__ == "__main__":
    main()
