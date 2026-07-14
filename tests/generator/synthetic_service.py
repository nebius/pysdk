"""Canonical all-types schema used by the synthetic generator service test."""

from __future__ import annotations

from collections.abc import Iterable

from google.protobuf import (
    any_pb2,
    descriptor_pb2,
    duration_pb2,
    empty_pb2,
    field_mask_pb2,
    struct_pb2,
    timestamp_pb2,
    wrappers_pb2,
)
from google.protobuf.compiler import plugin_pb2
from google.rpc import code_pb2, status_pb2

F = descriptor_pb2.FieldDescriptorProto

SCALARS: tuple[tuple[str, int, object], ...] = (
    ("double_value", F.TYPE_DOUBLE, 1.25),
    ("float_value", F.TYPE_FLOAT, -2.5),
    ("int32_value", F.TYPE_INT32, -123),
    ("int64_value", F.TYPE_INT64, -(2**40)),
    ("uint32_value", F.TYPE_UINT32, 123),
    ("uint64_value", F.TYPE_UINT64, 2**40),
    ("sint32_value", F.TYPE_SINT32, -456),
    ("sint64_value", F.TYPE_SINT64, -(2**41)),
    ("fixed32_value", F.TYPE_FIXED32, 789),
    ("fixed64_value", F.TYPE_FIXED64, 2**42),
    ("sfixed32_value", F.TYPE_SFIXED32, -789),
    ("sfixed64_value", F.TYPE_SFIXED64, -(2**42)),
    ("bool_value", F.TYPE_BOOL, True),
    ("string_value", F.TYPE_STRING, "synthetic"),
    ("bytes_value", F.TYPE_BYTES, b"\x00\xffsynthetic"),
)

WELL_KNOWN_TYPES: tuple[tuple[str, str], ...] = (
    ("any_value", ".google.protobuf.Any"),
    ("duration_value", ".google.protobuf.Duration"),
    ("empty_value", ".google.protobuf.Empty"),
    ("field_mask_value", ".google.protobuf.FieldMask"),
    ("struct_value", ".google.protobuf.Struct"),
    ("empty_struct_value", ".google.protobuf.Struct"),
    ("value_value", ".google.protobuf.Value"),
    ("list_value", ".google.protobuf.ListValue"),
    ("empty_list_value", ".google.protobuf.ListValue"),
    ("timestamp_value", ".google.protobuf.Timestamp"),
    ("bool_wrapper", ".google.protobuf.BoolValue"),
    ("bytes_wrapper", ".google.protobuf.BytesValue"),
    ("double_wrapper", ".google.protobuf.DoubleValue"),
    ("float_wrapper", ".google.protobuf.FloatValue"),
    ("int32_wrapper", ".google.protobuf.Int32Value"),
    ("int64_wrapper", ".google.protobuf.Int64Value"),
    ("string_wrapper", ".google.protobuf.StringValue"),
    ("uint32_wrapper", ".google.protobuf.UInt32Value"),
    ("uint64_wrapper", ".google.protobuf.UInt64Value"),
    ("status_value", ".google.rpc.Status"),
)

MAP_KEY_TYPES: tuple[int, ...] = (
    F.TYPE_STRING,
    F.TYPE_BOOL,
    F.TYPE_INT32,
    F.TYPE_INT64,
    F.TYPE_UINT32,
    F.TYPE_UINT64,
    F.TYPE_SINT32,
    F.TYPE_SINT64,
    F.TYPE_FIXED32,
    F.TYPE_FIXED64,
    F.TYPE_SFIXED32,
    F.TYPE_SFIXED64,
)


def _field(
    message: descriptor_pb2.DescriptorProto,
    name: str,
    number: int,
    type_: int,
    *,
    type_name: str = "",
    label: int = F.LABEL_OPTIONAL,
    oneof_index: int | None = None,
    proto3_optional: bool = False,
    json_name: str = "",
) -> descriptor_pb2.FieldDescriptorProto:
    field = message.field.add(
        name=name,
        number=number,
        type=type_,
        label=label,
        proto3_optional=proto3_optional,
    )
    if type_name:
        field.type_name = type_name
    if oneof_index is not None:
        field.oneof_index = oneof_index
    if json_name:
        field.json_name = json_name
    return field


def _map_field(
    message: descriptor_pb2.DescriptorProto,
    name: str,
    number: int,
    key_type: int,
    value_type: int,
    *,
    value_type_name: str = "",
) -> None:
    entry_name = "".join(part.capitalize() for part in name.split("_")) + "Entry"
    entry = message.nested_type.add(name=entry_name)
    entry.options.map_entry = True
    _field(entry, "key", 1, key_type)
    _field(entry, "value", 2, value_type, type_name=value_type_name)
    _field(
        message,
        name,
        number,
        F.TYPE_MESSAGE,
        type_name=f".synthetic.everything.v1.AllTypes.{entry_name}",
        label=F.LABEL_REPEATED,
    )


def _standard_files() -> Iterable[descriptor_pb2.FileDescriptorProto]:
    modules = (
        any_pb2,
        duration_pb2,
        empty_pb2,
        field_mask_pb2,
        struct_pb2,
        timestamp_pb2,
        wrappers_pb2,
        code_pb2,
        status_pb2,
    )
    return (
        descriptor_pb2.FileDescriptorProto.FromString(module.DESCRIPTOR.serialized_pb)
        for module in modules
    )


def synthetic_request(namespace: str) -> plugin_pb2.CodeGeneratorRequest:
    """Build one schema covering every supported public value and RPC shape."""
    file = descriptor_pb2.FileDescriptorProto(
        name="synthetic/everything/v1/all_types.proto",
        package="synthetic.everything.v1",
        syntax="proto3",
        dependency=[proto.name for proto in _standard_files()],
    )

    state = file.enum_type.add(name="State")
    state.value.add(name="STATE_UNSPECIFIED", number=0)
    state.value.add(name="STATE_READY", number=1)
    state.value.add(name="STATE_NEGATIVE", number=-1)

    child = file.message_type.add(name="Child")
    _field(child, "text", 1, F.TYPE_STRING)
    _field(child, "count", 2, F.TYPE_INT32)

    recursive = file.message_type.add(name="Recursive")
    _field(recursive, "value", 1, F.TYPE_STRING)
    _field(
        recursive,
        "next",
        2,
        F.TYPE_MESSAGE,
        type_name=".synthetic.everything.v1.Recursive",
    )

    all_types = file.message_type.add(name="AllTypes")
    all_types.oneof_decl.add(name="choice")
    number = 1
    for name, type_, _ in SCALARS:
        _field(all_types, name, number, type_)
        number += 1
    _field(
        all_types,
        "state",
        number,
        F.TYPE_ENUM,
        type_name=".synthetic.everything.v1.State",
    )
    number += 1
    _field(
        all_types,
        "child",
        number,
        F.TYPE_MESSAGE,
        type_name=".synthetic.everything.v1.Child",
    )
    number += 1
    _field(
        all_types,
        "recursive",
        number,
        F.TYPE_MESSAGE,
        type_name=".synthetic.everything.v1.Recursive",
    )
    _field(
        all_types,
        "display_label",
        19,
        F.TYPE_STRING,
        json_name="displayLabelCustom",
    )
    _field(
        all_types,
        "proto_reset_name",
        20,
        F.TYPE_STRING,
        json_name="protoResetCustom",
    )
    _field(
        all_types,
        "rpc_code",
        21,
        F.TYPE_ENUM,
        type_name=".google.rpc.Code",
    )

    number = 31
    for name, type_, _ in SCALARS:
        repeated = _field(
            all_types,
            f"repeated_{name}",
            number,
            type_,
            label=F.LABEL_REPEATED,
        )
        if name == "int32_value":
            repeated.options.packed = False
        number += 1
    _field(
        all_types,
        "repeated_state",
        number,
        F.TYPE_ENUM,
        type_name=".synthetic.everything.v1.State",
        label=F.LABEL_REPEATED,
    )
    number += 1
    _field(
        all_types,
        "repeated_child",
        number,
        F.TYPE_MESSAGE,
        type_name=".synthetic.everything.v1.Child",
        label=F.LABEL_REPEATED,
    )
    number += 1
    _field(
        all_types,
        "repeated_timestamp",
        number,
        F.TYPE_MESSAGE,
        type_name=".google.protobuf.Timestamp",
        label=F.LABEL_REPEATED,
    )

    number = 61
    for index, (name, type_, _) in enumerate(SCALARS):
        _map_field(
            all_types,
            f"map_{name}",
            number,
            MAP_KEY_TYPES[index % len(MAP_KEY_TYPES)],
            type_,
        )
        number += 1
    _map_field(
        all_types,
        "map_state",
        number,
        F.TYPE_STRING,
        F.TYPE_ENUM,
        value_type_name=".synthetic.everything.v1.State",
    )
    number += 1
    _map_field(
        all_types,
        "map_child",
        number,
        F.TYPE_STRING,
        F.TYPE_MESSAGE,
        value_type_name=".synthetic.everything.v1.Child",
    )
    number += 1
    _map_field(
        all_types,
        "map_timestamp",
        number,
        F.TYPE_STRING,
        F.TYPE_MESSAGE,
        value_type_name=".google.protobuf.Timestamp",
    )

    number = 91
    for name, type_name in WELL_KNOWN_TYPES:
        _field(all_types, name, number, F.TYPE_MESSAGE, type_name=type_name)
        number += 1

    number = 121
    for name, type_, _ in SCALARS:
        oneof_index = len(all_types.oneof_decl)
        optional_name = f"optional_{name}"
        all_types.oneof_decl.add(name=f"_{optional_name}")
        _field(
            all_types,
            optional_name,
            number,
            type_,
            oneof_index=oneof_index,
            proto3_optional=True,
        )
        number += 1
    oneof_index = len(all_types.oneof_decl)
    all_types.oneof_decl.add(name="_optional_state")
    _field(
        all_types,
        "optional_state",
        number,
        F.TYPE_ENUM,
        type_name=".synthetic.everything.v1.State",
        oneof_index=oneof_index,
        proto3_optional=True,
    )

    _field(all_types, "choice_text", 151, F.TYPE_STRING, oneof_index=0)
    _field(
        all_types,
        "choice_child",
        152,
        F.TYPE_MESSAGE,
        type_name=".synthetic.everything.v1.Child",
        oneof_index=0,
    )
    _field(
        all_types,
        "choice_timestamp",
        153,
        F.TYPE_MESSAGE,
        type_name=".google.protobuf.Timestamp",
        oneof_index=0,
    )

    service = file.service.add(name="AllTypesService")
    service.method.add(
        name="Echo",
        input_type=".synthetic.everything.v1.AllTypes",
        output_type=".synthetic.everything.v1.AllTypes",
    )
    service.method.add(
        name="Expand",
        input_type=".synthetic.everything.v1.AllTypes",
        output_type=".synthetic.everything.v1.AllTypes",
        server_streaming=True,
    )
    service.method.add(
        name="Collect",
        input_type=".synthetic.everything.v1.AllTypes",
        output_type=".synthetic.everything.v1.AllTypes",
        client_streaming=True,
    )
    service.method.add(
        name="Chat",
        input_type=".synthetic.everything.v1.AllTypes",
        output_type=".synthetic.everything.v1.AllTypes",
        client_streaming=True,
        server_streaming=True,
    )

    standard = list(_standard_files())
    return plugin_pb2.CodeGeneratorRequest(
        proto_file=[*standard, file],
        file_to_generate=[file.name],
        parameter=f"package_prefix={namespace},partition=all,jobs=1",
    )
