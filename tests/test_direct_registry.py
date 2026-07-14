"""Namespace isolation and Any tests for the direct message registry."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from nebius.base.protos.codec import BYTES, INT32, INT64, STRING
from nebius.base.protos.direct import Field, Message
from nebius.base.protos.json_format import JsonError, message_to_value, parse_value
from nebius.base.protos.registry import MessageReference, Registry, RegistryFragment


@dataclass(frozen=True)
class _Namespace:
    registry: Registry
    any_type: type[Message]
    payload_type: type[Message]
    timestamp_type: type[Message]


def _namespace(label: str) -> _Namespace:
    any_type = type(
        f"{label}Any",
        (Message,),
        {"__PROTO_FULL_NAME__": "google.protobuf.Any"},
    )
    any_type.__FIELDS__ = (
        Field("type_url", "type_url", 1, STRING),
        Field("value", "value", 2, BYTES),
    )
    payload_type = type(
        f"{label}Payload",
        (Message,),
        {"__PROTO_FULL_NAME__": "direct.test.Payload"},
    )
    payload_type.__FIELDS__ = (
        Field("text", "text", 1, STRING),
        Field("count", "count", 2, INT32),
    )
    timestamp_type = type(
        f"{label}Timestamp",
        (Message,),
        {"__PROTO_FULL_NAME__": "google.protobuf.Timestamp"},
    )
    timestamp_type.__FIELDS__ = (
        Field("seconds", "seconds", 1, INT64),
        Field("nanos", "nanos", 2, INT32),
    )
    references = {
        "google.protobuf.Any": MessageReference(factory=lambda: any_type),
        "google.protobuf.Timestamp": MessageReference(factory=lambda: timestamp_type),
        "direct.test.Payload": MessageReference(factory=lambda: payload_type),
    }
    registry = Registry(
        references,
        any_type=MessageReference(factory=lambda: any_type),
    )
    any_type.__REGISTRY__ = registry
    payload_type.__REGISTRY__ = registry
    timestamp_type.__REGISTRY__ = registry
    return _Namespace(registry, any_type, payload_type, timestamp_type)


def _value(message: Message, name: str):
    return message._get_field(message.__class__._fields_by_proto_name()[name])


def test_registry_composes_package_fragments_and_rejects_duplicates() -> None:
    namespace = _namespace("Fragmented")
    references = namespace.registry.symbols
    fragments = (
        RegistryFragment(
            symbols={"google.protobuf.Any": references["google.protobuf.Any"]},
            enum_symbols={},
            serialized_files=(),
        ),
        RegistryFragment(
            symbols={
                "direct.test.Payload": references["direct.test.Payload"],
                "google.protobuf.Timestamp": references["google.protobuf.Timestamp"],
            },
            enum_symbols={},
            serialized_files=(),
        ),
    )
    registry = Registry.from_fragments(fragments)
    namespace.any_type.__REGISTRY__ = registry
    namespace.payload_type.__REGISTRY__ = registry
    namespace.timestamp_type.__REGISTRY__ = registry
    assert registry.message_class("direct.test.Payload") is namespace.payload_type

    duplicate = RegistryFragment(
        symbols={"direct.test.Payload": references["direct.test.Payload"]},
        enum_symbols={},
        serialized_files=(),
    )
    try:
        Registry.from_fragments((*fragments, duplicate))
    except ValueError as error:
        assert "duplicate protobuf message name" in str(error)
    else:
        raise AssertionError("duplicate fragment symbol was accepted")


def test_registry_pack_unpack_and_json_round_trip() -> None:
    namespace = _namespace("Public")
    payload = namespace.payload_type(text="hello", count=7)
    packed = namespace.registry.pack_any(
        payload, type_url_prefix="example.invalid/custom/"
    )
    assert _value(packed, "type_url") == "example.invalid/custom/direct.test.Payload"
    assert namespace.registry.unpack_any(packed).SerializeToString() == (
        payload.SerializeToString()
    )

    expected = {
        "@type": "example.invalid/custom/direct.test.Payload",
        "text": "hello",
        "count": 7,
    }
    assert message_to_value(packed) == expected
    parsed = parse_value(expected, namespace.any_type())
    unpacked = namespace.registry.unpack_any(
        parsed, expected_type=namespace.payload_type
    )
    assert _value(unpacked, "text") == "hello"
    assert _value(unpacked, "count") == 7


def test_registry_unpack_does_not_invoke_generated_constructor(monkeypatch) -> None:
    namespace = _namespace("InternalDecode")
    payload = namespace.payload_type(text="server detail", count=3)
    packed = namespace.registry.pack_any(payload)

    def user_constructor(_self, *args, **kwargs) -> None:
        raise AssertionError("internal Any decoding invoked the user constructor")

    monkeypatch.setattr(namespace.payload_type, "__init__", user_constructor)
    unpacked = namespace.registry.unpack_any(packed)

    assert type(unpacked) is namespace.payload_type
    assert _value(unpacked, "text") == "server detail"
    assert _value(unpacked, "count") == 3


def test_registry_internal_decode_suppresses_deprecation_warning(caplog) -> None:
    from nebius.api.nebius.common.error.v1alpha1 import REGISTRY, ServiceError

    caplog.set_level(logging.WARNING, logger="deprecation")
    payload = ServiceError(service="legacy.service", code="legacy-code")
    packed = REGISTRY.pack_any(payload)
    caplog.clear()

    unpacked = REGISTRY.unpack_any(packed)

    assert isinstance(unpacked, ServiceError)
    assert unpacked.service == "legacy.service"
    assert unpacked.code == "legacy-code"
    assert caplog.records == []


def test_any_well_known_value_envelope_and_nested_any() -> None:
    namespace = _namespace("Internal")
    stamp = namespace.timestamp_type(seconds=1, nanos=123_000_000)
    packed_stamp = namespace.registry.pack_any(stamp)
    stamp_json = {
        "@type": "type.googleapis.com/google.protobuf.Timestamp",
        "value": "1970-01-01T00:00:01.123Z",
    }
    assert message_to_value(packed_stamp) == stamp_json
    parsed_stamp = parse_value(stamp_json, namespace.any_type())
    assert namespace.registry.unpack_any(parsed_stamp).SerializeToString() == (
        stamp.SerializeToString()
    )

    nested = namespace.registry.pack_any(packed_stamp)
    assert message_to_value(nested) == {
        "@type": "type.googleapis.com/google.protobuf.Any",
        "value": stamp_json,
    }


def test_registry_identity_isolates_same_proto_names() -> None:
    public = _namespace("Public")
    internal = _namespace("Internal")
    public_payload = public.payload_type(text="public")
    internal_payload = internal.payload_type(text="internal")

    public_unpacked = public.registry.unpack_any(
        public.registry.pack_any(public_payload)
    )
    assert type(public_unpacked) is public.payload_type
    assert (
        type(internal.registry.unpack_any(internal.registry.pack_any(internal_payload)))
        is internal.payload_type
    )
    for registry, foreign in (
        (public.registry, internal_payload),
        (internal.registry, public_payload),
    ):
        try:
            registry.pack_any(foreign)
        except ValueError:
            pass
        else:
            raise AssertionError("registry packed a foreign namespace message")


def test_any_empty_malformed_unknown_and_expected_type_errors() -> None:
    namespace = _namespace("Errors")
    assert message_to_value(namespace.any_type()) == {}
    empty = parse_value({}, namespace.any_type())
    assert _value(empty, "type_url") == ""
    assert _value(empty, "value") == b""

    invalid_values = (
        {"value": "missing type"},
        {"@type": "missing/slash/unknown.Type"},
        {"@type": "malformed"},
        {"@type": "type.googleapis.com/direct.test.Payload", "unknown": 1},
    )
    for value in invalid_values:
        try:
            parse_value(value, namespace.any_type())
        except JsonError:
            pass
        else:
            raise AssertionError(f"invalid Any JSON was accepted: {value!r}")

    packed = namespace.registry.pack_any(namespace.payload_type())
    try:
        namespace.registry.unpack_any(packed, expected_type=namespace.timestamp_type)
    except ValueError:
        pass
    else:
        raise AssertionError("Any expected-type mismatch was accepted")


def test_registry_symbol_mapping_is_immutable_and_validated() -> None:
    namespace = _namespace("Frozen")
    try:
        namespace.registry.symbols["new.Message"] = MessageReference(
            factory=lambda: namespace.payload_type
        )
    except TypeError:
        pass
    else:
        raise AssertionError("registry symbol mapping was mutable")

    for type_url in ("", "no-slash", "/direct.test.Payload", "prefix/"):
        try:
            Registry.type_name(type_url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"malformed type URL was accepted: {type_url!r}")
