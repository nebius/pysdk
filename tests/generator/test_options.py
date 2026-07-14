from __future__ import annotations

import pytest
from google.protobuf import descriptor_pb2

from nebius_generator.errors import GeneratorError
from nebius_generator.options import (
    bool_option,
    iter_wire_fields,
    nested_string_option,
    repeated_varints,
)


def _varint(value: int) -> bytes:
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _field(number: int, wire_type: int, value: bytes | int) -> bytes:
    result = bytearray(_varint((number << 3) | wire_type))
    if wire_type == 0:
        assert isinstance(value, int)
        result.extend(_varint(value))
    elif wire_type == 2:
        assert isinstance(value, bytes)
        result.extend(_varint(len(value)))
        result.extend(value)
    else:
        raise AssertionError(f"unsupported test wire type {wire_type}")
    return bytes(result)


def test_unknown_extensions_are_read_without_registration() -> None:
    name_settings = _field(3, 2, b"RenamedService")
    raw = b"".join(
        (
            _field(1191, 2, b"compute"),
            _field(1195, 2, name_settings),
            _field(1197, 0, 2),
            _field(1197, 2, _varint(3) + _varint(4)),
        )
    )
    options = descriptor_pb2.MethodOptions()
    options.MergeFromString(raw)

    assert nested_string_option(options, 1195, 3) == "RenamedService"
    assert repeated_varints(options, 1197) == (2, 3, 4)


def test_boolean_unknown_option_uses_last_value() -> None:
    options = descriptor_pb2.FieldOptions()
    options.MergeFromString(
        _field(1192, 0, 0) + _field(1192, 0, 1) + _field(1192, 2, b"\x00")
    )

    assert bool_option(options, 1192)
    assert not bool_option(options, 1193)


def test_unrelated_unknown_groups_are_skipped() -> None:
    group = _varint((10 << 3) | 3) + _field(1, 0, 7) + _varint((10 << 3) | 4)
    options = descriptor_pb2.FieldOptions()
    options.MergeFromString(group + _field(1192, 0, 1))

    assert bool_option(options, 1192)


@pytest.mark.parametrize(
    "payload, message",
    [
        (b"\x00", "invalid protobuf option field number"),
        (b"\x08\x80", "truncated protobuf option varint"),
        (b"\x0a\x02x", "truncated length-delimited"),
        (b"\x0b", "unterminated protobuf option group"),
        (b"\x0c", "unexpected protobuf option end-group"),
        (b"\x0b\x14", "mismatched protobuf option end-group"),
        (b"\x80\x80\x80\x80\x80\x80\x80\x80\x80\x02", "exceeds 64 bits"),
        (_varint(1 << 32), "invalid protobuf option field number"),
    ],
)
def test_malformed_options_fail_deterministically(payload: bytes, message: str) -> None:
    with pytest.raises(GeneratorError, match=message):
        tuple(iter_wire_fields(payload))


def test_deeply_nested_groups_fail_in_band() -> None:
    payload = b"\x0b" * 101 + b"\x0c" * 101

    with pytest.raises(GeneratorError, match="group nesting exceeds limit"):
        tuple(iter_wire_fields(payload))
