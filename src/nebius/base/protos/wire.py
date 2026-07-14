"""Low-level protobuf wire encoding and decoding primitives."""

from __future__ import annotations

import math
import struct
from collections.abc import Callable, Iterable
from typing import TypeVar

from google.protobuf.message import DecodeError

WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LENGTH_DELIMITED = 2
WIRE_START_GROUP = 3
WIRE_END_GROUP = 4
WIRE_FIXED32 = 5

_MAX_FIELD_NUMBER = (1 << 29) - 1
_MAX_UINT32 = (1 << 32) - 1
_MAX_UINT64 = (1 << 64) - 1

T = TypeVar("T")


def _signed(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    mask = (1 << bits) - 1
    value &= mask
    return value - (1 << bits) if value & sign else value


def _zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


class BinaryReader:
    """Read primitive values from one protobuf-encoded byte sequence."""

    __slots__ = ("_data", "_max_depth", "_pos")

    def __init__(
        self,
        data: bytes | bytearray | memoryview,
        *,
        max_depth: int = 100,
        max_bytes: int | None = None,
    ) -> None:
        if max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        self._data = memoryview(data).cast("B")
        if max_bytes is not None and len(self._data) > max_bytes:
            raise DecodeError("protobuf input exceeds the configured byte limit")
        self._max_depth = max_depth
        self._pos = 0

    @property
    def position(self) -> int:
        """Current byte offset."""
        return self._pos

    @property
    def remaining(self) -> int:
        """Number of unread bytes."""
        return len(self._data) - self._pos

    def eof(self) -> bool:
        """Return whether the input was consumed completely."""
        return self._pos == len(self._data)

    def raw_bytes(self, start: int, end: int | None = None) -> bytes:
        """Return an already-read byte range without changing the position."""
        stop = self._pos if end is None else end
        if start < 0 or stop < start or stop > self._pos:
            raise ValueError("raw protobuf range was not fully read")
        return bytes(self._data[start:stop])

    def _read_exact(self, size: int) -> memoryview:
        if size < 0 or size > self.remaining:
            raise DecodeError("truncated protobuf field")
        start = self._pos
        self._pos += size
        return self._data[start : self._pos]

    def read_varint(self) -> int:
        """Read one unsigned 64-bit varint."""
        value = 0
        for shift in range(0, 70, 7):
            byte = int(self._read_exact(1)[0])
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value & _MAX_UINT64
        raise DecodeError("protobuf varint exceeds 10 bytes")

    def read_tag(self) -> tuple[int, int, int]:
        """Return ``(field_number, wire_type, tag_start)``."""
        start = self._pos
        tag = 0
        for shift in range(0, 35, 7):
            byte = int(self._read_exact(1)[0])
            if shift == 28 and byte > 0x0F:
                raise DecodeError("protobuf tag exceeds 32 bits")
            tag |= (byte & 0x7F) << shift
            if byte < 0x80:
                break
        else:
            raise DecodeError("protobuf tag exceeds 5 bytes")
        field_number = tag >> 3
        wire_type = tag & 7
        if field_number == 0 or field_number > _MAX_FIELD_NUMBER:
            raise DecodeError("invalid protobuf field number")
        if wire_type > WIRE_FIXED32:
            raise DecodeError("invalid protobuf wire type")
        return field_number, wire_type, start

    def read_int32(self) -> int:
        return _signed(self.read_varint(), 32)

    def read_int64(self) -> int:
        return _signed(self.read_varint(), 64)

    def read_uint32(self) -> int:
        return self.read_varint() & _MAX_UINT32

    def read_uint64(self) -> int:
        return self.read_varint()

    def read_sint32(self) -> int:
        return _signed(_zigzag_decode(self.read_varint() & _MAX_UINT32), 32)

    def read_sint64(self) -> int:
        return _signed(_zigzag_decode(self.read_varint()), 64)

    def read_bool(self) -> bool:
        return self.read_varint() != 0

    def read_fixed32(self) -> int:
        return int(struct.unpack("<I", self._read_exact(4))[0])

    def read_sfixed32(self) -> int:
        return int(struct.unpack("<i", self._read_exact(4))[0])

    def read_float(self) -> float:
        return float(struct.unpack("<f", self._read_exact(4))[0])

    def read_fixed64(self) -> int:
        return int(struct.unpack("<Q", self._read_exact(8))[0])

    def read_sfixed64(self) -> int:
        return int(struct.unpack("<q", self._read_exact(8))[0])

    def read_double(self) -> float:
        return float(struct.unpack("<d", self._read_exact(8))[0])

    def read_bytes(self) -> bytes:
        return bytes(self._read_exact(self.read_varint()))

    def read_string(self) -> str:
        try:
            return self.read_bytes().decode("utf-8")
        except UnicodeDecodeError as error:
            raise DecodeError("invalid UTF-8 in protobuf string") from error

    def read_packed(self, read_value: Callable[[], T]) -> list[T]:
        """Read a length-delimited sequence with the supplied primitive reader."""
        size = self.read_varint()
        end = self._pos + size
        if end > len(self._data):
            raise DecodeError("truncated packed protobuf field")
        values: list[T] = []
        while self._pos < end:
            before = self._pos
            values.append(read_value())
            if self._pos <= before or self._pos > end:
                raise DecodeError("packed protobuf value exceeds its field")
        return values

    def skip_field(
        self,
        field_number: int,
        wire_type: int,
        tag_start: int,
    ) -> bytes:
        """Skip a field and return its complete original encoded bytes."""
        self._skip_value(field_number, wire_type)
        return bytes(self._data[tag_start : self._pos])

    def _skip_value(self, field_number: int, wire_type: int) -> None:
        if wire_type == WIRE_VARINT:
            self.read_varint()
        elif wire_type == WIRE_FIXED64:
            self._read_exact(8)
        elif wire_type == WIRE_LENGTH_DELIMITED:
            self._read_exact(self.read_varint())
        elif wire_type == WIRE_START_GROUP:
            self._skip_group(field_number)
        elif wire_type == WIRE_END_GROUP:
            raise DecodeError("unexpected protobuf end-group tag")
        elif wire_type == WIRE_FIXED32:
            self._read_exact(4)
        else:
            raise DecodeError("invalid protobuf wire type")

    def _skip_group(self, field_number: int) -> None:
        groups = [field_number]
        if len(groups) > self._max_depth:
            raise DecodeError("protobuf group nesting exceeds the configured limit")
        while groups:
            nested_number, nested_wire, _ = self.read_tag()
            if nested_wire == WIRE_START_GROUP:
                if len(groups) >= self._max_depth:
                    raise DecodeError(
                        "protobuf group nesting exceeds the configured limit"
                    )
                groups.append(nested_number)
            elif nested_wire == WIRE_END_GROUP:
                if nested_number != groups[-1]:
                    raise DecodeError("mismatched protobuf end-group tag")
                groups.pop()
            else:
                self._skip_value(nested_number, nested_wire)


class BinaryWriter:
    """Append primitive protobuf values to a byte buffer."""

    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data = bytearray()

    def to_bytes(self) -> bytes:
        return bytes(self._data)

    def write_raw(self, data: bytes | bytearray | memoryview) -> None:
        self._data.extend(data)

    def write_varint(self, value: int) -> None:
        if value < 0 or value > _MAX_UINT64:
            raise ValueError("varint value is outside uint64 range")
        while value > 0x7F:
            self._data.append((value & 0x7F) | 0x80)
            value >>= 7
        self._data.append(value)

    def write_tag(self, field_number: int, wire_type: int) -> None:
        if field_number <= 0 or field_number > _MAX_FIELD_NUMBER:
            raise ValueError("invalid protobuf field number")
        if wire_type < WIRE_VARINT or wire_type > WIRE_FIXED32:
            raise ValueError("invalid protobuf wire type")
        self.write_varint((field_number << 3) | wire_type)

    def write_int32(self, value: int) -> None:
        if not -(1 << 31) <= value < (1 << 31):
            raise ValueError("int32 value is outside its range")
        self.write_varint(value & _MAX_UINT64)

    def write_int64(self, value: int) -> None:
        if not -(1 << 63) <= value < (1 << 63):
            raise ValueError("int64 value is outside its range")
        self.write_varint(value & _MAX_UINT64)

    def write_uint32(self, value: int) -> None:
        if not 0 <= value <= _MAX_UINT32:
            raise ValueError("uint32 value is outside its range")
        self.write_varint(value)

    def write_uint64(self, value: int) -> None:
        self.write_varint(value)

    def write_sint32(self, value: int) -> None:
        if not -(1 << 31) <= value < (1 << 31):
            raise ValueError("sint32 value is outside its range")
        self.write_varint(((value << 1) ^ (value >> 31)) & _MAX_UINT32)

    def write_sint64(self, value: int) -> None:
        if not -(1 << 63) <= value < (1 << 63):
            raise ValueError("sint64 value is outside its range")
        self.write_varint(((value << 1) ^ (value >> 63)) & _MAX_UINT64)

    def write_bool(self, value: bool) -> None:
        self.write_varint(1 if value else 0)

    def write_fixed32(self, value: int) -> None:
        self._data.extend(struct.pack("<I", value))

    def write_sfixed32(self, value: int) -> None:
        self._data.extend(struct.pack("<i", value))

    def write_float(self, value: float) -> None:
        try:
            encoded = struct.pack("<f", value)
        except OverflowError:
            encoded = struct.pack("<f", math.copysign(math.inf, value))
        self._data.extend(encoded)

    def write_fixed64(self, value: int) -> None:
        self._data.extend(struct.pack("<Q", value))

    def write_sfixed64(self, value: int) -> None:
        self._data.extend(struct.pack("<q", value))

    def write_double(self, value: float) -> None:
        self._data.extend(struct.pack("<d", value))

    def write_bytes(self, value: bytes | bytearray | memoryview) -> None:
        self.write_varint(len(value))
        self._data.extend(value)

    def write_string(self, value: str) -> None:
        self.write_bytes(value.encode("utf-8"))

    def write_packed(
        self,
        values: Iterable[T],
        write_value: Callable[["BinaryWriter", T], None],
    ) -> None:
        nested = BinaryWriter()
        for value in values:
            write_value(nested, value)
        self.write_bytes(nested.to_bytes())
