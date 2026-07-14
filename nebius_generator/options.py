"""Read protobuf options without registering their extensions globally."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from .errors import GeneratorError


class SerializableOptions(Protocol):
    def SerializeToString(  # noqa: N802 - protobuf compatibility protocol
        self,
        *,
        deterministic: bool = ...,
    ) -> bytes: ...


@dataclass(frozen=True)
class WireField:
    """A single decoded protobuf field."""

    number: int
    wire_type: int
    value: int | bytes


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for index, shift in enumerate(range(0, 70, 7)):
        if offset >= len(data):
            raise GeneratorError("truncated protobuf option varint")
        byte = data[offset]
        offset += 1
        if index == 9 and byte > 1:
            raise GeneratorError("protobuf option varint exceeds 64 bits")
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
    raise GeneratorError("protobuf option varint exceeds 64 bits")


def _consume_value(
    data: bytes,
    offset: int,
    number: int,
    wire_type: int,
    group_depth: int = 0,
) -> tuple[int | bytes, int]:
    if wire_type == 0:
        return _read_varint(data, offset)
    if wire_type == 1:
        end = offset + 8
        if end > len(data):
            raise GeneratorError("truncated fixed64 protobuf option")
        return data[offset:end], end
    if wire_type == 2:
        size, offset = _read_varint(data, offset)
        end = offset + size
        if end > len(data):
            raise GeneratorError("truncated length-delimited protobuf option")
        return data[offset:end], end
    if wire_type == 3:
        if group_depth >= 100:
            raise GeneratorError("protobuf option group nesting exceeds limit")
        start = offset
        while offset < len(data):
            key, offset = _read_varint(data, offset)
            nested_number = key >> 3
            nested_wire_type = key & 7
            if not 0 < nested_number < (1 << 29):
                raise GeneratorError("invalid protobuf option field number")
            if nested_wire_type == 4:
                if nested_number != number:
                    raise GeneratorError("mismatched protobuf option end-group")
                return data[start:offset], offset
            _, offset = _consume_value(
                data,
                offset,
                nested_number,
                nested_wire_type,
                group_depth + 1,
            )
        raise GeneratorError("unterminated protobuf option group")
    if wire_type == 4:
        raise GeneratorError("unexpected protobuf option end-group")
    if wire_type == 5:
        end = offset + 4
        if end > len(data):
            raise GeneratorError("truncated fixed32 protobuf option")
        return data[offset:end], end
    raise GeneratorError(f"unsupported protobuf option wire type {wire_type}")


def iter_wire_fields(data: bytes) -> Iterator[WireField]:
    """Yield primitive fields from a serialized options message."""
    offset = 0
    while offset < len(data):
        key, offset = _read_varint(data, offset)
        number = key >> 3
        wire_type = key & 7
        if not 0 < number < (1 << 29):
            raise GeneratorError("invalid protobuf option field number")
        value, offset = _consume_value(data, offset, number, wire_type)
        yield WireField(number, wire_type, value)


def option_bytes(options: SerializableOptions | bytes) -> bytes:
    """Return stable serialized bytes for provider or frozen option objects."""
    if isinstance(options, bytes):
        return options
    return options.SerializeToString(deterministic=True)


def length_delimited(
    options: SerializableOptions | bytes,
    field_number: int,
) -> tuple[bytes, ...]:
    return tuple(
        field.value
        for field in iter_wire_fields(option_bytes(options))
        if field.number == field_number
        and field.wire_type == 2
        and isinstance(field.value, bytes)
    )


def repeated_varints(
    options: SerializableOptions | bytes,
    field_number: int,
) -> tuple[int, ...]:
    """Read repeated integers in unpacked or packed encoding."""
    result: list[int] = []
    for field in iter_wire_fields(option_bytes(options)):
        if field.number != field_number:
            continue
        if field.wire_type == 0 and isinstance(field.value, int):
            result.append(field.value)
        elif field.wire_type == 2 and isinstance(field.value, bytes):
            for packed in iter_wire_fields(_as_synthetic_fields(field.value)):
                if not isinstance(packed.value, int):
                    raise GeneratorError("invalid packed protobuf option")
                result.append(packed.value)
    return tuple(result)


def _as_synthetic_fields(data: bytes) -> bytes:
    """Prefix packed varints with a temporary field-one key for reuse."""
    result = bytearray()
    offset = 0
    while offset < len(data):
        _, end = _read_varint(data, offset)
        result.append(8)
        result.extend(data[offset:end])
        offset = end
    return bytes(result)


def bool_option(
    options: SerializableOptions | bytes,
    field_number: int,
) -> bool:
    values = tuple(
        field.value
        for field in iter_wire_fields(option_bytes(options))
        if field.number == field_number
        and field.wire_type == 0
        and isinstance(field.value, int)
    )
    return bool(values[-1]) if values else False


def nested_string_option(
    options: SerializableOptions | bytes,
    extension_number: int,
    nested_field_number: int,
) -> str:
    """Read a string inside a message-valued option extension."""
    result = ""
    for message in length_delimited(options, extension_number):
        values = length_delimited(message, nested_field_number)
        if values:
            try:
                result = values[-1].decode("utf-8")
            except UnicodeDecodeError as error:
                raise GeneratorError("protobuf option string is not UTF-8") from error
    return result
