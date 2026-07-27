"""Differential ProtoJSON tests for direct messages."""

from __future__ import annotations

import math

from google.protobuf import json_format as provider_json_format
from test_direct_message import (
    REF_REQUIRED_EXTENSION,
    REFERENCE_CHILD,
    REFERENCE_EXTENSION_HOST,
    REFERENCE_LEGACY,
    REFERENCE_SAMPLE,
    REQUIRED_EXTENSION,
    Child,
    ExtensionHost,
    Legacy,
    Sample,
)

from nebius.base.protos.codec import FLOAT
from nebius.base.protos.direct import Field, Message
from nebius.base.protos.json_format import (
    JsonError,
    message_to_dict,
    message_to_json,
    parse_dict,
)


def _sample_from_dict(data: dict[str, object], *, ignore: bool = False) -> Sample:
    return parse_dict(data, Sample(), ignore_unknown_fields=ignore)


class _FloatMessage(Message):
    __PROTO_FULL_NAME__ = "direct.test.FloatMessage"

    @property
    def value(self) -> float:
        return self._get_field(_FLOAT_VALUE)


_FLOAT_VALUE = Field("value", "value", 1, FLOAT)
_FloatMessage.__FIELDS__ = (_FLOAT_VALUE,)


def test_protojson_matches_reference_for_populated_message() -> None:
    reference = REFERENCE_SAMPLE(
        count=12,
        title="display",
        child=REFERENCE_CHILD(value=7, note="nested"),
        nums=[-1, 0, 9],
        children=[REFERENCE_CHILD(value=1), REFERENCE_CHILD(note="two")],
        text="selected",
        optional_count=0,
        labels={"a": 1},
        child_map={"child": REFERENCE_CHILD(value=3)},
        state=1,
        big=(1 << 60) + 3,
        payload=b"\x00\xffbytes",
        ratio=math.inf,
        active=True,
    )
    expected = provider_json_format.MessageToDict(reference)
    direct = Sample.FromString(reference.SerializeToString(deterministic=True))
    assert message_to_dict(direct) == expected

    parsed = parse_dict(expected, Sample())
    round_tripped = REFERENCE_SAMPLE.FromString(
        parsed.SerializeToString(deterministic=True)
    )
    assert round_tripped == reference


def test_protojson_output_options_match_reference() -> None:
    reference = REFERENCE_SAMPLE(state=1)
    direct = Sample.FromString(reference.SerializeToString(deterministic=True))
    for preserving_names in (False, True):
        expected = provider_json_format.MessageToDict(
            reference,
            preserving_proto_field_name=preserving_names,
            always_print_fields_with_no_presence=True,
            use_integers_for_enums=True,
        )
        assert (
            message_to_dict(
                direct,
                preserving_proto_field_name=preserving_names,
                always_print_fields_with_no_presence=True,
                use_integers_for_enums=True,
            )
            == expected
        )


def test_protojson_aliases_follow_reference_order_and_merge_messages() -> None:
    assert _sample_from_dict({"displayTitle": "json"}).title == "json"
    assert _sample_from_dict({"title": "proto"}).title == "proto"
    assert (
        _sample_from_dict({"displayTitle": "json", "title": "proto"}).title == "proto"
    )
    merged = _sample_from_dict({"directChild": {"value": 1}, "child": {"note": "x"}})
    assert merged.child.value == 1
    assert merged.child.note == "x"

    replaced = _sample_from_dict(
        {
            "childMap": {"first": {"value": 1}},
            "child_map": {"second": {"value": 2}},
        }
    )
    assert list(replaced.child_map) == ["second"]

    try:
        _sample_from_dict({"text": "one", "selectedChild": {"value": 2}})
    except JsonError:
        pass
    else:
        raise AssertionError("multiple oneof members were accepted")


def test_protojson_rejects_exact_duplicate_and_unknown_keys() -> None:
    for payload in (
        '{"count": 1, "count": 2}',
        '{"labels": {"same": 1, "same": 2}}',
    ):
        try:
            Sample.from_json(payload)
        except JsonError:
            pass
        else:
            raise AssertionError("duplicate JSON key was accepted")

    try:
        _sample_from_dict({"unknown": 1})
    except JsonError:
        pass
    else:
        raise AssertionError("unknown JSON field was accepted")
    assert _sample_from_dict({"unknown": 1, "count": 2}, ignore=True).count == 2


def test_protojson_nulls_and_invalid_scalar_forms() -> None:
    cleared = _sample_from_dict(
        {"count": None, "nums": None, "optionalCount": None, "child": None}
    )
    assert cleared.count == 0
    assert cleared.nums == []
    assert cleared.optional_count is None
    assert not cleared.HasField("child")

    for data in (
        {"count": True},
        {"count": 1 << 40},
        {"nums": [1, None]},
        {"payload": "not base64!"},
        {"state": "MISSING"},
        {"active": 1},
    ):
        try:
            _sample_from_dict(data)
        except JsonError:
            pass
        else:
            raise AssertionError(f"invalid ProtoJSON value was accepted: {data!r}")


def test_protojson_message_and_map_values_are_owned() -> None:
    child = Child(value=1)
    direct = _sample_from_dict(
        {
            "child": message_to_dict(child),
            "children": [message_to_dict(child)],
            "childMap": {"key": message_to_dict(child)},
        }
    )
    child.value = 2
    assert direct.child.value == 1
    assert direct.children[0].value == 1
    assert direct.child_map["key"].value == 1


def test_protojson_extensions_use_canonical_bracketed_full_name() -> None:
    reference = REFERENCE_EXTENSION_HOST()
    reference.Extensions[REF_REQUIRED_EXTENSION].name = "valid"
    direct = ExtensionHost()
    direct.set_extension(REQUIRED_EXTENSION, Legacy(name="valid"))
    expected = provider_json_format.MessageToDict(reference)
    assert message_to_dict(direct) == expected
    assert list(expected) == ["[direct.test.required_extension]"]

    parsed = parse_dict(expected, ExtensionHost())
    assert parsed.get_extension(REQUIRED_EXTENSION).name == "valid"
    assert parsed.IsInitialized()


def test_protojson_text_round_trip() -> None:
    direct = Sample(
        title="text",
        big=-(1 << 60),
        payload=b"payload",
        ratio=-math.inf,
        state=9,
    )
    payload = message_to_json(direct, indent=None, sort_keys=True)
    parsed = Sample.from_json(payload)
    assert parsed.title == "text"
    assert parsed.big == -(1 << 60)
    assert parsed.payload == b"payload"
    assert parsed.ratio == -math.inf
    assert parsed.state == 9


def test_protojson_reference_scalar_boundaries() -> None:
    forms = (("01", 1), ("-01", -1), ("+1", 1), ("1.0", 1), ("1e2", 100))
    for value, expected in forms:
        assert _sample_from_dict({"count": value}).count == expected
    assert _sample_from_dict({"state": "9"}).state == 9
    assert _sample_from_dict({"state": "MISSING"}, ignore=True).state == 0

    for payload in ('{"ratio": NaN}', '{"ratio": "nan"}'):
        try:
            Sample.from_json(payload)
        except JsonError:
            pass
        else:
            raise AssertionError(f"invalid non-finite float was accepted: {payload}")

    for value in ("inf", "-inf", "Inf", "1e400"):
        reference = REFERENCE_SAMPLE()
        provider_json_format.ParseDict({"ratio": value}, reference)
        assert _sample_from_dict({"ratio": value}).ratio == reference.ratio
    reference_bool = REFERENCE_SAMPLE()
    provider_json_format.ParseDict({"ratio": True}, reference_bool)
    assert _sample_from_dict({"ratio": True}).ratio == reference_bool.ratio
    for value in ("NAN", "Nan", "+nan", "-NaN"):
        assert math.isnan(_sample_from_dict({"ratio": value}).ratio)

    assert _sample_from_dict({"payload": "Y Q =="}).payload == b"a"
    assert _sample_from_dict({"payload": "YQ==="}).payload == b"a"

    for data in ({"title": "\ud800"}, {"labels": {1: 2}}):
        try:
            _sample_from_dict(data)
        except JsonError:
            pass
        else:
            raise AssertionError(f"invalid JSON-domain value was accepted: {data!r}")


def test_protojson_float32_distinguishes_python_floats_from_strings() -> None:
    for value in (3.4028235e38, 3.5e38, -3.5e38):
        try:
            parse_dict({"value": value}, _FloatMessage())
        except JsonError:
            pass
        else:
            raise AssertionError(f"out-of-range float32 was accepted: {value!r}")

    assert math.isinf(parse_dict({"value": "3.5e38"}, _FloatMessage()).value)
    assert math.isinf(parse_dict({"value": 10**100}, _FloatMessage()).value)


def test_ignored_unknown_enum_names_do_not_hide_invalid_closed_numbers() -> None:
    assert (
        list(
            parse_dict(
                {"states": ["MISSING"]},
                Legacy(),
                ignore_unknown_fields=True,
            ).states
        )
        == []
    )
    for value in (2, "2"):
        reference = REFERENCE_LEGACY()
        try:
            provider_json_format.ParseDict(
                {"states": [value]}, reference, ignore_unknown_fields=True
            )
        except provider_json_format.ParseError:
            pass
        else:
            raise AssertionError("reference unexpectedly accepted closed enum value")
        try:
            parse_dict({"states": [value]}, Legacy(), ignore_unknown_fields=True)
        except JsonError:
            pass
        else:
            raise AssertionError("invalid closed enum value was ignored")
