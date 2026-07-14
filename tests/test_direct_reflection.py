"""Registry-owned descriptor facade tests."""

from __future__ import annotations

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool

from nebius.base.protos.codec import BOOL, BYTES, STRING
from nebius.base.protos.direct import Field, Message
from nebius.base.protos.reflection import Reflection
from nebius.base.protos.registry import MessageReference, Registry


def _descriptors() -> tuple[bytes, bytes]:
    dependency = descriptor_pb2.FileDescriptorProto(
        name="direct/dependency.proto",
        package="direct.dep",
        syntax="proto3",
    )
    dependency.message_type.add(name="Dependency").field.add(
        name="name", number=1, label=1, type=9
    )

    main = descriptor_pb2.FileDescriptorProto(
        name="direct/main.proto",
        package="direct.test",
        syntax="proto2",
        dependency=[dependency.name],
        public_dependency=[0],
    )
    state = main.enum_type.add(name="State")
    state.options.allow_alias = True
    state.value.add(name="ZERO", number=0)
    state.value.add(name="ALSO_ZERO", number=0)
    state.value.add(name="READY", number=1)
    request = main.message_type.add(name="Request")
    request.extension_range.add(start=100, end=200)
    request.oneof_decl.add(name="choice")
    request.field.add(name="id", number=1, label=2, type=9)
    request.field.add(
        name="dependency",
        number=2,
        label=1,
        type=11,
        type_name=".direct.dep.Dependency",
        oneof_index=0,
    )
    nested = request.nested_type.add(name="Nested")
    nested.field.add(name="value", number=1, label=1, type=5)
    response = main.message_type.add(name="Response")
    response.field.add(
        name="state",
        number=1,
        label=1,
        type=14,
        type_name=".direct.test.State",
    )
    extension = main.extension.add(
        name="tag",
        number=100,
        label=1,
        type=9,
        extendee=".direct.test.Request",
    )
    extension.options.deprecated = True
    service = main.service.add(name="TestService")
    method = service.method.add(
        name="Watch",
        input_type=".direct.test.Request",
        output_type=".direct.test.Response",
        server_streaming=True,
    )
    method.options.deprecated = True
    return (
        dependency.SerializeToString(deterministic=True),
        main.SerializeToString(deterministic=True),
    )


def test_raw_descriptor_graph_links_without_provider_pool() -> None:
    decoded: list[tuple[str, bytes]] = []

    def decode(kind: str, payload: bytes) -> tuple[str, bytes]:
        decoded.append((kind, payload))
        return kind, payload

    reflection = Reflection(_descriptors(), decode)
    assert reflection._provider_pool is None
    file = reflection.files_by_name["direct/main.proto"]
    assert file.package == "direct.test"
    assert file.syntax == "proto2"
    assert [item.name for item in file.dependencies] == ["direct/dependency.proto"]
    assert file.public_dependencies == file.dependencies

    request = reflection.messages_by_name["direct.test.Request"]
    assert request.file is file
    assert request.fields_by_name["id"].has_presence
    dependency = request.fields_by_number[2]
    assert (
        dependency.message_type is reflection.messages_by_name["direct.dep.Dependency"]
    )
    assert dependency.containing_oneof is request.oneofs_by_name["choice"]
    assert request.nested_types_by_name["Nested"].containing_type is request
    assert request.extension_ranges == ((100, 200),)
    assert request.is_extendable
    assert request.fields_by_camelcase_name["dependency"] is dependency
    assert request.fields_by_name["id"].is_required
    assert request.fields_by_name["id"].default_value == ""

    enum = reflection.enums_by_name["direct.test.State"]
    assert enum.values_by_name["READY"].number == 1
    assert enum.values_by_number[0].name == "ZERO"
    assert len(enum.values) == 3
    assert enum.values[0].full_name == "direct.test.ZERO"

    service = reflection.services_by_name["direct.test.TestService"]
    method = service.methods_by_name["Watch"]
    assert method.input_type is request
    assert method.output_type.full_name == "direct.test.Response"
    assert method.server_streaming and not method.client_streaming

    extension = reflection.extensions_by_name["direct.test.tag"]
    assert extension.is_extension
    assert extension.containing_type is request
    assert file.extensions_by_name["tag"] is extension
    assert reflection._provider_pool is None

    option = method.GetOptions()
    assert option[0] == "google.protobuf.MethodOptions"
    assert decoded == [("google.protobuf.MethodOptions", option[1])]


def test_provider_descriptor_is_private_lazy_and_identity_separate() -> None:
    reflection = Reflection(_descriptors(), lambda kind, payload: (kind, payload))
    direct = reflection.messages_by_name["direct.test.Request"]
    provider = direct.provider_descriptor
    assert reflection._provider_pool is not None
    assert provider.full_name == direct.full_name
    assert provider is direct.provider_descriptor
    assert provider is not direct

    field = direct.fields_by_name["dependency"]
    assert field.provider_descriptor.full_name == field.full_name
    nested_field = reflection.messages_by_name[
        "direct.test.Request.Nested"
    ].fields_by_name["value"]
    assert nested_field.provider_descriptor.full_name == nested_field.full_name
    enum_value = reflection.enums_by_name["direct.test.State"].values[0]
    assert enum_value.provider_descriptor.name == enum_value.name
    method = reflection.services_by_name["direct.test.TestService"].methods_by_name[
        "Watch"
    ]
    assert method.provider_descriptor.full_name == method.full_name


def test_registry_decodes_direct_options_and_binds_message_descriptor() -> None:
    class AnyMessage(Message):
        __PROTO_FULL_NAME__ = "google.protobuf.Any"

    AnyMessage.__FIELDS__ = (
        Field("type_url", "type_url", 1, STRING),
        Field("value", "value", 2, BYTES),
    )

    class MethodOptions(Message):
        __PROTO_FULL_NAME__ = "google.protobuf.MethodOptions"

    MethodOptions.__FIELDS__ = (Field("deprecated", "deprecated", 33, BOOL),)

    class Request(Message):
        __PROTO_FULL_NAME__ = "direct.test.Request"

    references = {
        item.__PROTO_FULL_NAME__: MessageReference(factory=lambda item=item: item)
        for item in (AnyMessage, MethodOptions, Request)
    }
    registry = Registry(
        references,
        any_type=references[AnyMessage.__PROTO_FULL_NAME__],
        serialized_files=_descriptors(),
    )
    for item in (AnyMessage, MethodOptions, Request):
        item.__REGISTRY__ = registry

    descriptor = Request.get_descriptor()
    assert descriptor is registry.message_descriptor("direct.test.Request")
    method = registry.service_descriptor("direct.test.TestService").methods_by_name[
        "Watch"
    ]
    options = method.GetOptions()
    assert isinstance(options, MethodOptions)
    assert options._get_field(MethodOptions.__FIELDS__[0]) is True


def test_empty_package_enum_value_uses_file_scope() -> None:
    proto = descriptor_pb2.FileDescriptorProto(name="empty.proto", syntax="proto3")
    enum = proto.enum_type.add(name="State")
    enum.value.add(name="ZERO", number=0)
    reflection = Reflection(
        (proto.SerializeToString(deterministic=True),),
        lambda kind, payload: (kind, payload),
    )
    value = reflection.enums_by_name["State"].values[0]
    assert value.full_name == "ZERO"
    assert value.provider_descriptor.name == "ZERO"


def test_duplicate_file_names_are_rejected() -> None:
    first = descriptor_pb2.FileDescriptorProto(name="same.proto")
    second = descriptor_pb2.FileDescriptorProto(name="same.proto")
    with pytest.raises(ValueError, match="duplicate protobuf file name"):
        Reflection(
            (first.SerializeToString(), second.SerializeToString()),
            lambda kind, payload: (kind, payload),
        )


def test_duplicate_symbols_across_files_are_rejected() -> None:
    first = descriptor_pb2.FileDescriptorProto(name="first.proto", package="test")
    first.message_type.add(name="Collision")
    second = descriptor_pb2.FileDescriptorProto(name="second.proto", package="test")
    second.enum_type.add(name="Collision")
    with pytest.raises(ValueError, match="duplicate protobuf symbol 'test.Collision'"):
        Reflection(
            (first.SerializeToString(), second.SerializeToString()),
            lambda kind, payload: (kind, payload),
        )


def test_enum_values_share_their_containing_scope() -> None:
    proto = descriptor_pb2.FileDescriptorProto(name="enum.proto", package="test")
    for enum_name in ("First", "Second"):
        enum = proto.enum_type.add(name=enum_name)
        enum.value.add(name="COLLISION", number=0)
    with pytest.raises(ValueError, match="duplicate protobuf symbol 'test.COLLISION'"):
        Reflection(
            (proto.SerializeToString(),),
            lambda kind, payload: (kind, payload),
        )


@pytest.mark.parametrize("duplicate", ["field_name", "field_number", "oneof", "method"])
def test_duplicate_local_indices_are_rejected(duplicate: str) -> None:
    proto = descriptor_pb2.FileDescriptorProto(name="local.proto", package="test")
    message = proto.message_type.add(name="Message")
    if duplicate == "field_name":
        message.field.add(name="field", number=1, label=1, type=5)
        message.field.add(name="field", number=2, label=1, type=5)
    elif duplicate == "field_number":
        message.field.add(name="first", number=1, label=1, type=5)
        message.field.add(name="second", number=1, label=1, type=5)
    elif duplicate == "oneof":
        message.oneof_decl.add(name="choice")
        message.oneof_decl.add(name="choice")
    else:
        service = proto.service.add(name="Service")
        service.method.add(
            name="Call", input_type=".test.Message", output_type=".test.Message"
        )
        service.method.add(
            name="Call", input_type=".test.Message", output_type=".test.Message"
        )
    with pytest.raises(ValueError, match="duplicate"):
        Reflection(
            (proto.SerializeToString(),),
            lambda kind, payload: (kind, payload),
        )


def test_bytes_defaults_match_provider_c_unescape() -> None:
    defaults = (
        r"\?",
        r"\400",
        r"\777",
        r"\xA",
        r"\101",
        r"\\",
        r"\"",
        "é",
    )
    proto = descriptor_pb2.FileDescriptorProto(
        name="defaults.proto", package="test", syntax="proto2"
    )
    message = proto.message_type.add(name="Defaults")
    for index, default in enumerate(defaults, start=1):
        message.field.add(
            name=f"field_{index}",
            number=index,
            label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
            type=descriptor_pb2.FieldDescriptorProto.TYPE_BYTES,
            default_value=default,
        )
    raw = proto.SerializeToString(deterministic=True)
    direct = Reflection((raw,), lambda kind, payload: (kind, payload))
    provider = descriptor_pool.DescriptorPool().AddSerializedFile(raw)
    direct_fields = direct.messages_by_name["test.Defaults"].fields
    provider_fields = provider.message_types_by_name["Defaults"].fields
    assert [field.default_value for field in direct_fields] == [
        field.default_value for field in provider_fields
    ]


@pytest.mark.parametrize("default", [r"\x123", r"\x", r"\z", "trailing\\"])
def test_invalid_bytes_default_escapes_are_rejected(default: str) -> None:
    proto = descriptor_pb2.FileDescriptorProto(name="invalid-default.proto")
    message = proto.message_type.add(name="Message")
    message.field.add(name="field", number=1, label=1, type=12, default_value=default)
    with pytest.raises(ValueError):
        Reflection(
            (proto.SerializeToString(),),
            lambda kind, payload: (kind, payload),
        )
