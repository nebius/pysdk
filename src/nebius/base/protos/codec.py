"""Reusable value codecs for generated protobuf field dispatch."""

from __future__ import annotations

import math
import struct
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from .wire import (
    WIRE_FIXED32,
    WIRE_FIXED64,
    WIRE_LENGTH_DELIMITED,
    WIRE_VARINT,
    BinaryReader,
    BinaryWriter,
)

T = TypeVar("T")
_C_LONG_BITS = struct.calcsize("l") * 8


@dataclass(frozen=True)
class ValueCodec(Generic[T]):
    """Wire operations and ownership hooks for one protobuf value type."""

    wire_type: int
    read: Callable[[BinaryReader], T]
    write: Callable[[BinaryWriter, T], None]
    normalize: Callable[[object], T]
    default: Callable[[], T]
    packable: bool = True
    clone: Callable[[T], T] | None = None
    merge: Callable[[T, T], T] | None = None
    bind_mutation: Callable[[T, Callable[[], None]], None] | None = None
    deterministic_write: Callable[[BinaryWriter, T, bool], None] | None = None
    enum_values: frozenset[int] | None = None
    closed_enum: bool = False
    json_kind: str = "message"
    enum_names: Mapping[int, str] | None = None
    enum_numbers: Mapping[str, int] | None = None

    def copy(self, value: T) -> T:
        """Return an owned copy when the value type needs one."""
        if self.clone is None:
            return value
        return self.clone(value)

    def write_value(
        self, writer: BinaryWriter, value: T, *, deterministic: bool = False
    ) -> None:
        """Write a value, propagating deterministic mode when it matters."""
        if self.deterministic_write is not None:
            self.deterministic_write(writer, value, deterministic)
        else:
            self.write(writer, value)


def _integer_normalizer(
    name: str, minimum: int, maximum: int
) -> Callable[[object], int]:
    def normalize(value: object) -> int:
        if not isinstance(value, int):
            raise TypeError(f"{name} field requires int")
        if not minimum <= value <= maximum:
            raise ValueError(f"{name} value is outside its range")
        return int(value)

    return normalize


def _bool(value: object) -> bool:
    if not isinstance(value, int):
        raise TypeError("bool field requires bool or int")
    if not -(1 << (_C_LONG_BITS - 1)) <= value < (1 << (_C_LONG_BITS - 1)):
        raise OverflowError("bool integer is outside the platform C long range")
    return bool(value)


def _float(value: object) -> float:
    if not isinstance(value, (int, float)):
        raise TypeError("floating-point field requires int or float")
    return float(value)


def _float32(value: object) -> float:
    normalized = _float(value)
    try:
        encoded = struct.pack("<f", normalized)
    except OverflowError:
        encoded = struct.pack("<f", math.copysign(math.inf, normalized))
    return float(struct.unpack("<f", encoded)[0])


def _bytes(value: object) -> bytes:
    if not isinstance(value, bytes):
        raise TypeError("bytes field requires bytes")
    return value


def _string(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8")
    raise TypeError("string field requires str or UTF-8 bytes")


INT32 = ValueCodec(
    WIRE_VARINT,
    BinaryReader.read_int32,
    BinaryWriter.write_int32,
    _integer_normalizer("int32", -(1 << 31), (1 << 31) - 1),
    int,
    json_kind="int32",
)
INT64 = ValueCodec(
    WIRE_VARINT,
    BinaryReader.read_int64,
    BinaryWriter.write_int64,
    _integer_normalizer("int64", -(1 << 63), (1 << 63) - 1),
    int,
    json_kind="int64",
)
UINT32 = ValueCodec(
    WIRE_VARINT,
    BinaryReader.read_uint32,
    BinaryWriter.write_uint32,
    _integer_normalizer("uint32", 0, (1 << 32) - 1),
    int,
    json_kind="uint32",
)
UINT64 = ValueCodec(
    WIRE_VARINT,
    BinaryReader.read_uint64,
    BinaryWriter.write_uint64,
    _integer_normalizer("uint64", 0, (1 << 64) - 1),
    int,
    json_kind="uint64",
)
SINT32 = ValueCodec(
    WIRE_VARINT,
    BinaryReader.read_sint32,
    BinaryWriter.write_sint32,
    _integer_normalizer("sint32", -(1 << 31), (1 << 31) - 1),
    int,
    json_kind="int32",
)
SINT64 = ValueCodec(
    WIRE_VARINT,
    BinaryReader.read_sint64,
    BinaryWriter.write_sint64,
    _integer_normalizer("sint64", -(1 << 63), (1 << 63) - 1),
    int,
    json_kind="int64",
)
BOOL = ValueCodec(
    WIRE_VARINT,
    BinaryReader.read_bool,
    BinaryWriter.write_bool,
    _bool,
    bool,
    json_kind="bool",
)
FIXED32 = ValueCodec(
    WIRE_FIXED32,
    BinaryReader.read_fixed32,
    BinaryWriter.write_fixed32,
    _integer_normalizer("fixed32", 0, (1 << 32) - 1),
    int,
    json_kind="uint32",
)
SFIXED32 = ValueCodec(
    WIRE_FIXED32,
    BinaryReader.read_sfixed32,
    BinaryWriter.write_sfixed32,
    _integer_normalizer("sfixed32", -(1 << 31), (1 << 31) - 1),
    int,
    json_kind="int32",
)
FLOAT = ValueCodec(
    WIRE_FIXED32,
    BinaryReader.read_float,
    BinaryWriter.write_float,
    _float32,
    float,
    json_kind="float",
)
FIXED64 = ValueCodec(
    WIRE_FIXED64,
    BinaryReader.read_fixed64,
    BinaryWriter.write_fixed64,
    _integer_normalizer("fixed64", 0, (1 << 64) - 1),
    int,
    json_kind="uint64",
)
SFIXED64 = ValueCodec(
    WIRE_FIXED64,
    BinaryReader.read_sfixed64,
    BinaryWriter.write_sfixed64,
    _integer_normalizer("sfixed64", -(1 << 63), (1 << 63) - 1),
    int,
    json_kind="int64",
)
DOUBLE = ValueCodec(
    WIRE_FIXED64,
    BinaryReader.read_double,
    BinaryWriter.write_double,
    _float,
    float,
    json_kind="double",
)
BYTES = ValueCodec(
    WIRE_LENGTH_DELIMITED,
    BinaryReader.read_bytes,
    BinaryWriter.write_bytes,
    _bytes,
    bytes,
    packable=False,
    json_kind="bytes",
)
STRING = ValueCodec(
    WIRE_LENGTH_DELIMITED,
    BinaryReader.read_string,
    BinaryWriter.write_string,
    _string,
    str,
    packable=False,
    json_kind="string",
)


def enum_codec(
    values: Iterable[int],
    *,
    default: int = 0,
    closed: bool = False,
    names: Mapping[str, int] | None = None,
    enum_type: Callable[[], type[Any]] | None = None,
) -> ValueCodec[Any]:
    """Build an int32 wire codec with proto2/proto3 enum validation metadata."""
    known_values = frozenset(values)
    if default not in known_values:
        raise ValueError("enum default must be one of its declared values")
    integer = _integer_normalizer("enum", -(1 << 31), (1 << 31) - 1)

    def wrap(value: int) -> Any:
        return value if enum_type is None else enum_type()(value)

    def normalize(value: object) -> Any:
        normalized = integer(value)
        if closed and normalized not in known_values:
            raise ValueError("closed enum value is not declared")
        return wrap(normalized)

    def read(reader: BinaryReader) -> Any:
        return wrap(reader.read_int32())

    enum_numbers = dict(names or {})
    enum_names: dict[int, str] = {}
    for name, number in enum_numbers.items():
        enum_names.setdefault(number, name)

    return ValueCodec(
        WIRE_VARINT,
        read,
        BinaryWriter.write_int32,
        normalize,
        lambda: wrap(default),
        enum_values=known_values,
        closed_enum=closed,
        json_kind="enum",
        enum_names=enum_names,
        enum_numbers=enum_numbers,
    )
