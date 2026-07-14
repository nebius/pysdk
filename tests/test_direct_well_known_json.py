"""Differential ProtoJSON tests for direct well-known messages."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from google.protobuf import (
    duration_pb2,
    empty_pb2,
    field_mask_pb2,
    struct_pb2,
    timestamp_pb2,
    wrappers_pb2,
)
from google.protobuf import (
    json_format as provider_json_format,
)

from nebius.base.protos.codec import (
    BOOL,
    BYTES,
    DOUBLE,
    FLOAT,
    INT32,
    INT64,
    STRING,
    UINT32,
    UINT64,
    ValueCodec,
    enum_codec,
)
from nebius.base.protos.direct import Field, Message, message_codec
from nebius.base.protos.json_format import (
    JsonError,
    message_to_dict,
    message_to_value,
    parse_dict,
    parse_value,
)


class Timestamp(Message):
    __PROTO_FULL_NAME__ = "google.protobuf.Timestamp"


Timestamp.__FIELDS__ = (
    Field("seconds", "seconds", 1, INT64),
    Field("nanos", "nanos", 2, INT32),
)


class Duration(Message):
    __PROTO_FULL_NAME__ = "google.protobuf.Duration"


Duration.__FIELDS__ = (
    Field("seconds", "seconds", 1, INT64),
    Field("nanos", "nanos", 2, INT32),
)


class FieldMask(Message):
    __PROTO_FULL_NAME__ = "google.protobuf.FieldMask"


FieldMask.__FIELDS__ = (Field("paths", "paths", 1, STRING, repeated=True),)


class Empty(Message):
    __PROTO_FULL_NAME__ = "google.protobuf.Empty"


class Struct(Message):
    __PROTO_FULL_NAME__ = "google.protobuf.Struct"


class Value(Message):
    __PROTO_FULL_NAME__ = "google.protobuf.Value"


class ListValue(Message):
    __PROTO_FULL_NAME__ = "google.protobuf.ListValue"


VALUE_CODEC = message_codec(lambda: Value)
STRUCT_CODEC = message_codec(lambda: Struct)
LIST_VALUE_CODEC = message_codec(lambda: ListValue)
Struct.__FIELDS__ = (Field("fields", "fields", 1, VALUE_CODEC, map_key_codec=STRING),)
Value.__FIELDS__ = (
    Field(
        "null_value",
        "null_value",
        1,
        enum_codec((0,), names={"NULL_VALUE": 0}),
        oneof="kind",
    ),
    Field("number_value", "number_value", 2, DOUBLE, oneof="kind"),
    Field("string_value", "string_value", 3, STRING, oneof="kind"),
    Field("bool_value", "bool_value", 4, BOOL, oneof="kind"),
    Field("struct_value", "struct_value", 5, STRUCT_CODEC, oneof="kind"),
    Field("list_value", "list_value", 6, LIST_VALUE_CODEC, oneof="kind"),
)
ListValue.__FIELDS__ = (Field("values", "values", 1, VALUE_CODEC, repeated=True),)


class WktEnvelope(Message):
    __PROTO_FULL_NAME__ = "direct.test.WktEnvelope"


TIMESTAMP_CODEC = message_codec(lambda: Timestamp)
WktEnvelope.__FIELDS__ = (
    Field("stamp", "stamp", 1, TIMESTAMP_CODEC),
    Field("stamps", "stamps", 2, TIMESTAMP_CODEC, repeated=True),
    Field("stamps_by_name", "stamps_by_name", 3, TIMESTAMP_CODEC, map_key_codec=STRING),
    Field("value", "value", 4, VALUE_CODEC),
    Field("values", "values", 5, VALUE_CODEC, repeated=True),
    Field("values_by_name", "values_by_name", 6, VALUE_CODEC, map_key_codec=STRING),
)


def _wrapper(name: str, codec: ValueCodec[Any]) -> type[Message]:
    wrapper = type(
        name,
        (Message,),
        {"__PROTO_FULL_NAME__": f"google.protobuf.{name}"},
    )
    wrapper.__FIELDS__ = (Field("value", "value", 1, codec),)
    return wrapper


WRAPPERS = (
    (_wrapper("BoolValue", BOOL), wrappers_pb2.BoolValue, True),
    (_wrapper("BytesValue", BYTES), wrappers_pb2.BytesValue, b"bytes"),
    (_wrapper("DoubleValue", DOUBLE), wrappers_pb2.DoubleValue, 1.25),
    (_wrapper("FloatValue", FLOAT), wrappers_pb2.FloatValue, 1.25),
    (_wrapper("Int32Value", INT32), wrappers_pb2.Int32Value, -12),
    (_wrapper("Int64Value", INT64), wrappers_pb2.Int64Value, -(1 << 50)),
    (_wrapper("StringValue", STRING), wrappers_pb2.StringValue, "text"),
    (_wrapper("UInt32Value", UINT32), wrappers_pb2.UInt32Value, 12),
    (_wrapper("UInt64Value", UINT64), wrappers_pb2.UInt64Value, 1 << 50),
)


def _from_provider(direct_type: type[Message], provider: Any) -> Message:
    return direct_type.FromString(provider.SerializeToString(deterministic=True))


def _assert_parse_matches(
    value: Any, direct_type: type[Message], provider_type: type[Any]
) -> None:
    reference = provider_type()
    provider_json_format.ParseDict(value, reference)
    direct = parse_value(value, direct_type())
    assert direct.SerializeToString(deterministic=True) == reference.SerializeToString(
        deterministic=True
    )


def test_timestamp_json_matches_reference() -> None:
    cases = (
        timestamp_pb2.Timestamp(seconds=0),
        timestamp_pb2.Timestamp(seconds=-62_135_596_800),
        timestamp_pb2.Timestamp(seconds=-1, nanos=1),
        timestamp_pb2.Timestamp(seconds=1, nanos=123_000_000),
        timestamp_pb2.Timestamp(seconds=253_402_300_799, nanos=999_999_999),
    )
    for reference in cases:
        direct = _from_provider(Timestamp, reference)
        assert message_to_value(direct) == provider_json_format.MessageToDict(reference)

    for value in (
        "1970-01-01T00:00:00Z",
        "1969-12-31T23:59:59.000000001Z",
        "2000-01-01T01:02:03.123456789+01:30",
        "1970-01-01T00:00:00+99:99",
        "1970-01-01T00:00:00.Z",
        "1970-01-01T00:00:00+1:2",
    ):
        _assert_parse_matches(value, Timestamp, timestamp_pb2.Timestamp)
    assert Timestamp.from_json('"1970-01-01T00:00:01Z"').SerializeToString() == (
        Timestamp(seconds=1).SerializeToString()
    )


def test_duration_json_matches_reference() -> None:
    cases = (
        duration_pb2.Duration(),
        duration_pb2.Duration(seconds=-1, nanos=-1),
        duration_pb2.Duration(nanos=-123_000_000),
        duration_pb2.Duration(seconds=315_576_000_000),
    )
    for reference in cases:
        direct = _from_provider(Duration, reference)
        assert message_to_value(direct) == provider_json_format.MessageToDict(reference)
    for value in (
        "0s",
        "-0.000000001s",
        "+12.345s",
        "1.1234567896s",
        "1.1e-2s",
        "315576000000s",
    ):
        _assert_parse_matches(value, Duration, duration_pb2.Duration)


def test_timestamp_and_duration_reject_reference_invalid_values() -> None:
    pairs: Iterable[tuple[Any, type[Message], type[Any]]] = (
        ("1970-01-01T00:00:00", Timestamp, timestamp_pb2.Timestamp),
        ("1970-01-01T00:00:00.1234567890Z", Timestamp, timestamp_pb2.Timestamp),
        ("315576000001s", Duration, duration_pb2.Duration),
        ("1e2s", Duration, duration_pb2.Duration),
        (" -1.1s", Duration, duration_pb2.Duration),
    )
    for value, direct_type, provider_type in pairs:
        try:
            provider_json_format.ParseDict(value, provider_type())
        except provider_json_format.ParseError:
            pass
        else:
            raise AssertionError("reference unexpectedly accepted invalid WKT JSON")
        try:
            parse_value(value, direct_type())
        except JsonError:
            pass
        else:
            raise AssertionError("direct runtime accepted invalid WKT JSON")


def test_field_mask_json_matches_reference() -> None:
    reference = field_mask_pb2.FieldMask(
        paths=["foo_bar", "nested.child_name", "ip_v6_address"]
    )
    direct = _from_provider(FieldMask, reference)
    value = provider_json_format.MessageToDict(reference)
    assert message_to_value(direct) == value
    _assert_parse_matches(value, FieldMask, field_mask_pb2.FieldMask)


def test_struct_value_and_list_value_match_reference() -> None:
    value = {
        "null": None,
        "bool": True,
        "number": 1.25,
        "string": "text",
        "object": {"nested": 2},
        "list": [None, False, "item", {"key": "value"}],
    }
    _assert_parse_matches(value, Struct, struct_pb2.Struct)
    direct = parse_value(value, Struct())
    assert message_to_value(direct) == value
    assert message_to_value(Struct.from_json('{"nested": [null, true]}')) == {
        "nested": [None, True]
    }

    for scalar in (None, False, 1.5, "text", {"a": 1}, [None, 2]):
        _assert_parse_matches(scalar, Value, struct_pb2.Value)
        assert message_to_value(parse_value(scalar, Value())) == scalar


def test_value_rejects_non_finite_numbers() -> None:
    for value in (math.nan, math.inf, -math.inf):
        try:
            parse_value(value, Value())
        except JsonError:
            pass
        else:
            raise AssertionError("non-finite Value number was accepted")

        direct = parse_value(0, Value())
        direct._set_field(Value.__FIELDS__[1], value)
        try:
            message_to_value(direct)
        except JsonError:
            pass
        else:
            raise AssertionError("non-finite Value number was emitted")


def test_all_wrapper_json_forms_match_reference() -> None:
    for direct_type, provider_type, value in WRAPPERS:
        reference = provider_type(value=value)
        direct = _from_provider(direct_type, reference)
        expected = provider_json_format.MessageToDict(reference)
        assert message_to_value(direct) == expected
        _assert_parse_matches(expected, direct_type, provider_type)
    for direct_type, provider_type, _ in WRAPPERS[2:4]:
        _assert_parse_matches(True, direct_type, provider_type)


def test_empty_json_matches_reference() -> None:
    assert message_to_value(Empty()) == provider_json_format.MessageToDict(
        empty_pb2.Empty()
    )
    _assert_parse_matches({}, Empty, empty_pb2.Empty)


def test_well_known_values_work_in_ordinary_fields_and_containers() -> None:
    data = {
        "stamp": "1970-01-01T00:00:01Z",
        "stamps": ["1970-01-01T00:00:02Z"],
        "stampsByName": {"end": "1970-01-01T00:00:03Z"},
        "value": None,
        "values": [None, {"nested": True}],
        "valuesByName": {"null": None, "number": 1.5},
    }
    direct = parse_dict(data, WktEnvelope())
    assert message_to_dict(direct) == data
