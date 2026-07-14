"""Compatibility facade over the SDK's committed generated API."""

from __future__ import annotations

from nebius.api._registry import REGISTRY as _API_REGISTRY
from nebius.api.google.protobuf import (
    FieldDescriptorProto as _GeneratedFieldDescriptorProto,
)
from nebius.api.google.protobuf import FileDescriptorProto
from nebius.api.google.protobuf.compiler import (
    CodeGeneratorRequest,
    CodeGeneratorResponse,
)
from nebius.base.protos.direct import Message

FrozenMessage = Message
GeneratedFile = CodeGeneratorResponse.File


class FieldDescriptorProto:
    """Protobuf field constants retained for existing generator call sites."""

    TYPE_DOUBLE = int(_GeneratedFieldDescriptorProto.Type.TYPE_DOUBLE)
    TYPE_FLOAT = int(_GeneratedFieldDescriptorProto.Type.TYPE_FLOAT)
    TYPE_INT64 = int(_GeneratedFieldDescriptorProto.Type.TYPE_INT64)
    TYPE_UINT64 = int(_GeneratedFieldDescriptorProto.Type.TYPE_UINT64)
    TYPE_INT32 = int(_GeneratedFieldDescriptorProto.Type.TYPE_INT32)
    TYPE_FIXED64 = int(_GeneratedFieldDescriptorProto.Type.TYPE_FIXED64)
    TYPE_FIXED32 = int(_GeneratedFieldDescriptorProto.Type.TYPE_FIXED32)
    TYPE_BOOL = int(_GeneratedFieldDescriptorProto.Type.TYPE_BOOL)
    TYPE_STRING = int(_GeneratedFieldDescriptorProto.Type.TYPE_STRING)
    TYPE_GROUP = int(_GeneratedFieldDescriptorProto.Type.TYPE_GROUP)
    TYPE_MESSAGE = int(_GeneratedFieldDescriptorProto.Type.TYPE_MESSAGE)
    TYPE_BYTES = int(_GeneratedFieldDescriptorProto.Type.TYPE_BYTES)
    TYPE_UINT32 = int(_GeneratedFieldDescriptorProto.Type.TYPE_UINT32)
    TYPE_ENUM = int(_GeneratedFieldDescriptorProto.Type.TYPE_ENUM)
    TYPE_SFIXED32 = int(_GeneratedFieldDescriptorProto.Type.TYPE_SFIXED32)
    TYPE_SFIXED64 = int(_GeneratedFieldDescriptorProto.Type.TYPE_SFIXED64)
    TYPE_SINT32 = int(_GeneratedFieldDescriptorProto.Type.TYPE_SINT32)
    TYPE_SINT64 = int(_GeneratedFieldDescriptorProto.Type.TYPE_SINT64)
    LABEL_OPTIONAL = int(_GeneratedFieldDescriptorProto.Label.LABEL_OPTIONAL)
    LABEL_REQUIRED = int(_GeneratedFieldDescriptorProto.Label.LABEL_REQUIRED)
    LABEL_REPEATED = int(_GeneratedFieldDescriptorProto.Label.LABEL_REPEATED)


def parse_request(data: bytes) -> CodeGeneratorRequest:
    return CodeGeneratorRequest.FromString(data)


def coerce_request(request: object) -> CodeGeneratorRequest:
    if isinstance(request, CodeGeneratorRequest):
        return request
    serializer = getattr(request, "SerializeToString", None)
    if not callable(serializer):
        raise TypeError("generator request is not serializable")
    return parse_request(serializer(deterministic=True))


_CANONICAL_STANDARD_FILES = (
    "google/protobuf/any.proto",
    "google/protobuf/api.proto",
    "google/protobuf/compiler/plugin.proto",
    "google/protobuf/descriptor.proto",
    "google/protobuf/duration.proto",
    "google/protobuf/empty.proto",
    "google/protobuf/field_mask.proto",
    "google/protobuf/source_context.proto",
    "google/protobuf/struct.proto",
    "google/protobuf/timestamp.proto",
    "google/protobuf/type.proto",
    "google/protobuf/wrappers.proto",
    "google/rpc/code.proto",
    "google/rpc/status.proto",
)


def normalize_request(request: CodeGeneratorRequest) -> CodeGeneratorRequest:
    """Replace Buf-bundled schemas with the committed SDK API edition."""
    normalized = CodeGeneratorRequest(request)
    canonical: dict[str, FileDescriptorProto] = {}
    for name in _CANONICAL_STANDARD_FILES:
        try:
            serialized = _API_REGISTRY.file_descriptor(name).serialized_pb
        except KeyError:
            # The committed API may not contain a newly adopted standard file
            # yet. The candidate captures it, and post-promotion regeneration
            # then supplies the canonical descriptor.
            continue
        canonical[name] = FileDescriptorProto.FromString(serialized)
    for collection in (
        normalized.proto_file,
        normalized.source_file_descriptors,
    ):
        for index, file in enumerate(collection):
            if file.name.startswith(("google/protobuf/", "google/rpc/")):
                file.ClearField("source_code_info")
            replacement = canonical.get(file.name)
            if replacement is not None:
                collection[index] = replacement
    return normalized


def include_file_descriptors(
    request: CodeGeneratorRequest, names: tuple[str, ...]
) -> None:
    """Add committed descriptors and their dependencies to a plugin request."""
    present = {file.name for file in request.proto_file}
    pending = list(names)
    while pending:
        name = pending.pop()
        if name in present:
            continue
        serialized = _API_REGISTRY.file_descriptor(name).serialized_pb
        file = FileDescriptorProto.FromString(serialized)
        request.proto_file.append(file)
        present.add(name)
        pending.extend(file.dependency)


def serialize_file_descriptor(file: FrozenMessage) -> bytes:
    normalized = FileDescriptorProto(file)
    normalized.ClearField("source_code_info")
    return normalized.SerializeToString(deterministic=True)
