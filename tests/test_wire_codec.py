"""Differential tests for the direct protobuf wire primitives."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.message import DecodeError, Message

from nebius.base.protos.wire import (
    WIRE_END_GROUP,
    WIRE_FIXED32,
    WIRE_FIXED64,
    WIRE_LENGTH_DELIMITED,
    WIRE_START_GROUP,
    WIRE_VARINT,
    BinaryReader,
    BinaryWriter,
)


def _scalar_message() -> type[Message]:
    file_proto = descriptor_pb2.FileDescriptorProto(
        name="wire_test.proto",
        package="wire.test",
        syntax="proto3",
    )
    message = file_proto.message_type.add(name="Scalars")
    field_types = (
        descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
        descriptor_pb2.FieldDescriptorProto.TYPE_INT64,
        descriptor_pb2.FieldDescriptorProto.TYPE_UINT32,
        descriptor_pb2.FieldDescriptorProto.TYPE_UINT64,
        descriptor_pb2.FieldDescriptorProto.TYPE_SINT32,
        descriptor_pb2.FieldDescriptorProto.TYPE_SINT64,
        descriptor_pb2.FieldDescriptorProto.TYPE_BOOL,
        descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32,
        descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32,
        descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT,
        descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64,
        descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64,
        descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE,
        descriptor_pb2.FieldDescriptorProto.TYPE_BYTES,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    for number, field_type in enumerate(field_types, 1):
        message.field.add(
            name=f"field_{number}",
            number=number,
            label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
            type=field_type,
        )
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_proto)
    return message_factory.GetMessageClass(
        pool.FindMessageTypeByName("wire.test.Scalars")
    )


SCALARS = _scalar_message()


@pytest.mark.parametrize(
    ("number", "value", "wire_type", "write", "read"),
    (
        (1, -123, WIRE_VARINT, BinaryWriter.write_int32, BinaryReader.read_int32),
        (2, -(1 << 50), WIRE_VARINT, BinaryWriter.write_int64, BinaryReader.read_int64),
        (
            3,
            (1 << 32) - 1,
            WIRE_VARINT,
            BinaryWriter.write_uint32,
            BinaryReader.read_uint32,
        ),
        (
            4,
            (1 << 64) - 1,
            WIRE_VARINT,
            BinaryWriter.write_uint64,
            BinaryReader.read_uint64,
        ),
        (5, -4567, WIRE_VARINT, BinaryWriter.write_sint32, BinaryReader.read_sint32),
        (
            6,
            -(1 << 45),
            WIRE_VARINT,
            BinaryWriter.write_sint64,
            BinaryReader.read_sint64,
        ),
        (7, True, WIRE_VARINT, BinaryWriter.write_bool, BinaryReader.read_bool),
        (
            8,
            0xFEEDBEEF,
            WIRE_FIXED32,
            BinaryWriter.write_fixed32,
            BinaryReader.read_fixed32,
        ),
        (
            9,
            -1234567,
            WIRE_FIXED32,
            BinaryWriter.write_sfixed32,
            BinaryReader.read_sfixed32,
        ),
        (10, 1.5, WIRE_FIXED32, BinaryWriter.write_float, BinaryReader.read_float),
        (
            11,
            0xFEEDBEEFDEADBEEF,
            WIRE_FIXED64,
            BinaryWriter.write_fixed64,
            BinaryReader.read_fixed64,
        ),
        (
            12,
            -(1 << 55),
            WIRE_FIXED64,
            BinaryWriter.write_sfixed64,
            BinaryReader.read_sfixed64,
        ),
        (
            13,
            -123.25,
            WIRE_FIXED64,
            BinaryWriter.write_double,
            BinaryReader.read_double,
        ),
        (
            14,
            b"\x00\xffbytes",
            WIRE_LENGTH_DELIMITED,
            BinaryWriter.write_bytes,
            BinaryReader.read_bytes,
        ),
        (
            15,
            "héllo",
            WIRE_LENGTH_DELIMITED,
            BinaryWriter.write_string,
            BinaryReader.read_string,
        ),
    ),
)
def test_scalar_encoding_matches_reference(
    number: int,
    value: object,
    wire_type: int,
    write: Callable[[BinaryWriter, object], None],
    read: Callable[[BinaryReader], object],
) -> None:
    reference = SCALARS()
    setattr(reference, f"field_{number}", value)
    expected = reference.SerializeToString(deterministic=True)

    writer = BinaryWriter()
    writer.write_tag(number, wire_type)
    write(writer, value)
    assert writer.to_bytes() == expected

    reader = BinaryReader(expected)
    assert reader.read_tag()[:2] == (number, wire_type)
    assert read(reader) == value
    assert reader.eof()


def _tag(number: int, wire_type: int) -> bytes:
    writer = BinaryWriter()
    writer.write_tag(number, wire_type)
    return writer.to_bytes()


def test_unknown_group_is_preserved_as_one_raw_chunk() -> None:
    raw = b"".join(
        (
            _tag(10, WIRE_START_GROUP),
            _tag(1, WIRE_VARINT),
            b"\x96\x01",
            _tag(11, WIRE_START_GROUP),
            _tag(2, WIRE_FIXED32),
            b"\x01\x02\x03\x04",
            _tag(11, WIRE_END_GROUP),
            _tag(10, WIRE_END_GROUP),
        )
    )
    reader = BinaryReader(raw)
    field_number, wire_type, start = reader.read_tag()
    assert reader.skip_field(field_number, wire_type, start) == raw
    assert reader.eof()


def test_packed_reader_and_writer() -> None:
    writer = BinaryWriter()
    writer.write_packed([1, 150, 30_000], BinaryWriter.write_uint32)
    payload = writer.to_bytes()
    reader = BinaryReader(payload)
    assert reader.read_packed(reader.read_uint32) == [1, 150, 30_000]
    assert reader.eof()


def test_varint_parser_matches_reference_overflow_truncation() -> None:
    payload = b"\xff" * 9 + b"\x02"
    reference = SCALARS.FromString(_tag(4, WIRE_VARINT) + payload)
    reader = BinaryReader(payload)
    assert reader.read_uint64() == reference.field_4 == (1 << 63) - 1


def test_tag_parser_has_reference_compatible_uint32_boundary() -> None:
    accepted = b"\x8a\x80\x80\x80\x00\x00"
    SCALARS.FromString(accepted)
    reader = BinaryReader(accepted)
    field_number, wire_type, start = reader.read_tag()
    assert (field_number, wire_type) == (1, WIRE_LENGTH_DELIMITED)
    assert reader.skip_field(field_number, wire_type, start) == accepted

    for rejected in (
        b"\x8a\x80\x80\x80\x80\x00\x00",
        b"\x8a\x80\x80\x80\x10\x00",
    ):
        with pytest.raises(DecodeError):
            BinaryReader(rejected).read_tag()
        with pytest.raises(DecodeError):
            SCALARS.FromString(rejected)


def test_float32_overflow_matches_reference_infinity() -> None:
    reference = SCALARS(field_10=1e100)
    writer = BinaryWriter()
    writer.write_tag(10, WIRE_FIXED32)
    writer.write_float(1e100)
    assert writer.to_bytes() == reference.SerializeToString(deterministic=True)


@pytest.mark.parametrize(
    ("method", "value"),
    (
        (BinaryWriter.write_int32, -(1 << 31) - 1),
        (BinaryWriter.write_int32, 1 << 31),
        (BinaryWriter.write_int64, -(1 << 63) - 1),
        (BinaryWriter.write_int64, 1 << 63),
        (BinaryWriter.write_uint32, -1),
        (BinaryWriter.write_uint32, 1 << 32),
        (BinaryWriter.write_uint64, -1),
        (BinaryWriter.write_uint64, 1 << 64),
        (BinaryWriter.write_sint32, -(1 << 31) - 1),
        (BinaryWriter.write_sint32, 1 << 31),
        (BinaryWriter.write_sint64, -(1 << 63) - 1),
        (BinaryWriter.write_sint64, 1 << 63),
    ),
)
def test_integer_writer_rejects_out_of_range_values(
    method: Callable[[BinaryWriter, int], None], value: int
) -> None:
    with pytest.raises(ValueError):
        method(BinaryWriter(), value)


def test_invalid_utf8_and_packed_boundary_are_rejected() -> None:
    with pytest.raises(DecodeError, match="UTF-8"):
        BinaryReader(b"\x01\xff").read_string()

    with pytest.raises(DecodeError, match="packed"):
        reader = BinaryReader(b"\x01\x96\x01")
        reader.read_packed(reader.read_uint32)


@pytest.mark.parametrize(
    "payload",
    (
        b"\x80",
        b"\x80" * 10 + b"\x00",
        b"\x00",
        _tag(1, WIRE_LENGTH_DELIMITED) + b"\x05abc",
        _tag(1, WIRE_FIXED32) + b"abc",
        _tag(1, WIRE_FIXED64) + b"abcdefg",
        _tag(2, WIRE_END_GROUP),
        _tag(2, WIRE_START_GROUP),
        _tag(2, WIRE_START_GROUP) + _tag(3, WIRE_END_GROUP),
    ),
)
def test_malformed_input_is_rejected(payload: bytes) -> None:
    reader = BinaryReader(payload)
    with pytest.raises(DecodeError):
        field_number, wire_type, start = reader.read_tag()
        reader.skip_field(field_number, wire_type, start)


def test_group_depth_and_input_size_limits() -> None:
    nested = b"".join(
        (
            _tag(1, WIRE_START_GROUP),
            _tag(2, WIRE_START_GROUP),
            _tag(2, WIRE_END_GROUP),
            _tag(1, WIRE_END_GROUP),
        )
    )
    reader = BinaryReader(nested, max_depth=1)
    field_number, wire_type, start = reader.read_tag()
    with pytest.raises(DecodeError, match="nesting"):
        reader.skip_field(field_number, wire_type, start)

    with pytest.raises(DecodeError, match="byte limit"):
        BinaryReader(nested, max_bytes=len(nested) - 1)


def test_group_skipping_does_not_depend_on_python_recursion() -> None:
    depth = 1_100
    nested = b"".join(
        _tag(number, WIRE_START_GROUP) for number in range(1, depth + 1)
    ) + b"".join(_tag(number, WIRE_END_GROUP) for number in range(depth, 0, -1))
    reader = BinaryReader(nested, max_depth=depth)
    field_number, wire_type, start = reader.read_tag()
    assert reader.skip_field(field_number, wire_type, start) == nested

    limited = BinaryReader(nested, max_depth=depth - 1)
    field_number, wire_type, start = limited.read_tag()
    with pytest.raises(DecodeError, match="nesting"):
        limited.skip_field(field_number, wire_type, start)
