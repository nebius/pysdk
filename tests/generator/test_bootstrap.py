"""Tests for the generator's committed SDK protobuf API."""

from google.protobuf import descriptor_pb2
from google.protobuf.compiler import plugin_pb2

from nebius.api._registry import REGISTRY
from nebius.api.google.protobuf import MessageOptions
from nebius.api.nebius import message_py_sdk
from nebius_generator.bootstrap import (
    include_file_descriptors,
    normalize_request,
    parse_request,
    serialize_file_descriptor,
)


def test_generated_bootstrap_parses_registered_annotation_extensions() -> None:
    parsed = MessageOptions.FromString(b"\xdaJ\x03\n\x01X")

    assert parsed.has_extension(message_py_sdk)
    assert parsed.Extensions[message_py_sdk].name == "X"


def test_generated_bootstrap_preserves_unknown_option_fields() -> None:
    raw = b"\x98\x06\x01"

    assert MessageOptions.FromString(raw).SerializeToString() == raw


def test_generated_bootstrap_preserves_unknown_request_fields() -> None:
    raw = b"\x98\x06\x01"

    assert parse_request(raw).SerializeToString() == raw


def test_generated_request_round_trips_provider_request() -> None:
    provider = descriptor_pb2.FileDescriptorProto(
        name="root.proto",
        dependency=["public.proto", "weak.proto"],
        public_dependency=[0],
        weak_dependency=[1],
    )
    serialized = provider.SerializeToString(deterministic=True)

    request = parse_request(b"\x7a" + bytes((len(serialized),)) + serialized)

    assert request.proto_file[0].SerializeToString(deterministic=True) == serialized


def test_generator_protocol_is_supplied_from_committed_api() -> None:
    request = parse_request(plugin_pb2.CodeGeneratorRequest().SerializeToString())

    include_file_descriptors(request, ("google/protobuf/compiler/plugin.proto",))

    files = {file.name for file in request.proto_file}
    assert "google/protobuf/compiler/plugin.proto" in files
    assert "google/protobuf/descriptor.proto" in files


def test_request_normalization_stabilizes_buf_owned_descriptors() -> None:
    provider = plugin_pb2.CodeGeneratorRequest(parameter="stable")
    provider.proto_file.add(
        name="google/protobuf/descriptor.proto",
        package="unstable.buf.version",
    ).source_code_info.location.add(path=[2], leading_comments="unstable")
    provider.proto_file.add(
        name="google/protobuf/compiler/plugin.proto",
        package="unstable.buf.version",
    )
    provider.proto_file.add(
        name="google/protobuf/timestamp.proto",
        package="unstable.buf.version",
    ).source_code_info.location.add(path=[2], leading_comments="unstable")
    provider.proto_file.add(
        name="google/rpc/status.proto",
        package="unstable.buf.version",
    ).source_code_info.location.add(path=[2], leading_comments="unstable")
    ordinary = provider.proto_file.add(name="acme/value.proto", package="acme")
    ordinary.source_code_info.location.add(path=[2], leading_comments="keep")
    request = parse_request(provider.SerializeToString(deterministic=True))

    normalized = normalize_request(request)

    assert request.proto_file[0].package == "unstable.buf.version"
    assert normalized.parameter == "stable"
    assert normalized.proto_file[0].package == "google.protobuf"
    assert not normalized.proto_file[0].source_code_info.location
    assert normalized.proto_file[1].package == "google.protobuf.compiler"
    assert normalized.proto_file[2].package == "google.protobuf"
    assert not normalized.proto_file[2].source_code_info.location
    assert normalized.proto_file[3].package == "google.rpc"
    assert not normalized.proto_file[3].source_code_info.location
    assert normalized.proto_file[4].package == "acme"
    assert normalized.proto_file[4].source_code_info.location[0].leading_comments == (
        "keep"
    )


def test_descriptor_normalization_drops_source_info() -> None:
    provider = descriptor_pb2.FileDescriptorProto(name="root.proto")
    provider.source_code_info.location.add(path=[4, 0], leading_comments="docs")
    request_bytes = provider.SerializeToString(deterministic=True)
    request = parse_request(b"\x7a" + bytes((len(request_bytes),)) + request_bytes)

    normalized = serialize_file_descriptor(request.proto_file[0])

    expected = descriptor_pb2.FileDescriptorProto(name="root.proto")
    assert normalized == expected.SerializeToString(deterministic=True)


def test_committed_api_registry_omits_source_info() -> None:
    assert REGISTRY.reflection is not None
    for file in REGISTRY.reflection.files_by_name.values():
        restored = descriptor_pb2.FileDescriptorProto.FromString(file.serialized_pb)
        assert not restored.HasField("source_code_info"), file.name
