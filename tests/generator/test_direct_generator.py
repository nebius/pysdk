"""Golden behavior for the provider-free Buf generator."""

from __future__ import annotations

import ast
import importlib
import json
import keyword
import os
import pickle
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from google.protobuf import (
    any_pb2,
    descriptor_pb2,
    descriptor_pool,
    duration_pb2,
    message_factory,
    timestamp_pb2,
)
from google.protobuf.compiler import plugin_pb2
from google.rpc import status_pb2
from grpc import StatusCode

from nebius.aio.request_status import rpc_status_from_call
from nebius.base.fieldmask import FieldKey, Mask
from nebius_generator import coordinator, emitter
from nebius_generator.bootstrap import parse_request
from nebius_generator.errors import GeneratorError
from nebius_generator.main import generate
from nebius_generator.model import Graph, Options

coordinate = coordinator.generate


def _implementation_source(
    response: plugin_pb2.CodeGeneratorResponse, package_path: str
) -> str:
    prefix = package_path.rstrip("/") + "/_impl_"
    return "\n".join(
        output.content
        for output in response.file
        if output.name.startswith(prefix) and output.name.endswith(".py")
    )


def _varint(value: int) -> bytes:
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _option_field(number: int, wire_type: int, value: int | bytes) -> bytes:
    result = bytearray(_varint((number << 3) | wire_type))
    if wire_type == 0:
        assert isinstance(value, int)
        result.extend(_varint(value))
    else:
        assert wire_type == 2 and isinstance(value, bytes)
        result.extend(_varint(len(value)))
        result.extend(value)
    return bytes(result)


def _name_option(extension: int, nested_field: int, name: str) -> bytes:
    return _option_field(
        extension,
        2,
        _option_field(nested_field, 2, name.encode()),
    )


def _field(
    message: descriptor_pb2.DescriptorProto,
    name: str,
    number: int,
    type_: int,
    *,
    type_name: str = "",
    label: int = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
    oneof_index: int | None = None,
) -> None:
    field = message.field.add(name=name, number=number, type=type_, label=label)
    if type_name:
        field.type_name = type_name
    if oneof_index is not None:
        field.oneof_index = oneof_index


def _add_public_annotation_schema(
    annotations: descriptor_pb2.FileDescriptorProto,
) -> None:
    """Add the policy-consumed public annotation subset to a synthetic schema."""
    annotations.dependency.append("google/protobuf/descriptor.proto")
    for message_name, name_number in (
        ("ServicePySDKSettings", 3),
        ("MethodPySDKSettings", 3),
        ("MessagePySDKSettings", 1),
        ("FieldPySDKSettings", 1),
        ("OneofPySDKSettings", 1),
        ("EnumPySDKSettings", 1),
        ("EnumValuePySDKSettings", 1),
    ):
        message = annotations.message_type.add(name=message_name)
        _field(
            message,
            "name",
            name_number,
            descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        )
    details = annotations.message_type.add(name="DeprecationDetails")
    for number, name in enumerate(
        ("effective_at", "description", "description_cli"), start=1
    ):
        _field(
            details,
            name,
            number,
            descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        )
    behavior = annotations.enum_type.add(name="MethodBehavior")
    for name, number in (
        ("METHOD_BEHAVIOR_UNSPECIFIED", 0),
        ("METHOD_UPDATER", 2),
        ("METHOD_PAGINATED", 3),
        ("METHOD_WITHOUT_GET", 4),
    ):
        behavior.value.add(name=name, number=number)
    for name, extendee, number, type_, type_name, label in (
        ("api_service_name", ".google.protobuf.ServiceOptions", 1191, 9, "", 1),
        (
            "service_py_sdk",
            ".google.protobuf.ServiceOptions",
            1195,
            11,
            ".nebius.ServicePySDKSettings",
            1,
        ),
        (
            "method_py_sdk",
            ".google.protobuf.MethodOptions",
            1195,
            11,
            ".nebius.MethodPySDKSettings",
            1,
        ),
        (
            "method_behavior",
            ".google.protobuf.MethodOptions",
            1197,
            14,
            ".nebius.MethodBehavior",
            3,
        ),
        (
            "message_py_sdk",
            ".google.protobuf.MessageOptions",
            1195,
            11,
            ".nebius.MessagePySDKSettings",
            1,
        ),
        (
            "field_py_sdk",
            ".google.protobuf.FieldOptions",
            1195,
            11,
            ".nebius.FieldPySDKSettings",
            1,
        ),
        ("sensitive", ".google.protobuf.FieldOptions", 1192, 8, "", 1),
        ("credentials", ".google.protobuf.FieldOptions", 1193, 8, "", 1),
        (
            "oneof_py_sdk",
            ".google.protobuf.OneofOptions",
            1192,
            11,
            ".nebius.OneofPySDKSettings",
            1,
        ),
        (
            "enum_py_sdk",
            ".google.protobuf.EnumOptions",
            1191,
            11,
            ".nebius.EnumPySDKSettings",
            1,
        ),
        (
            "enum_value_py_sdk",
            ".google.protobuf.EnumValueOptions",
            1195,
            11,
            ".nebius.EnumValuePySDKSettings",
            1,
        ),
        (
            "service_deprecation_details",
            ".google.protobuf.ServiceOptions",
            1194,
            11,
            ".nebius.DeprecationDetails",
            1,
        ),
        (
            "method_deprecation_details",
            ".google.protobuf.MethodOptions",
            1194,
            11,
            ".nebius.DeprecationDetails",
            1,
        ),
        (
            "message_deprecation_details",
            ".google.protobuf.MessageOptions",
            1194,
            11,
            ".nebius.DeprecationDetails",
            1,
        ),
        (
            "field_deprecation_details",
            ".google.protobuf.FieldOptions",
            1194,
            11,
            ".nebius.DeprecationDetails",
            1,
        ),
        (
            "enum_deprecation_details",
            ".google.protobuf.EnumOptions",
            1194,
            11,
            ".nebius.DeprecationDetails",
            1,
        ),
        (
            "enum_value_deprecation_details",
            ".google.protobuf.EnumValueOptions",
            1194,
            11,
            ".nebius.DeprecationDetails",
            1,
        ),
    ):
        annotations.extension.add(
            name=name,
            extendee=extendee,
            number=number,
            type=type_,
            type_name=type_name,
            label=label,
        )


def _request(namespace: str, partition: str = "all") -> plugin_pb2.CodeGeneratorRequest:
    common = descriptor_pb2.FileDescriptorProto(
        name="acme/common.proto", package="acme.common", syntax="proto3"
    )
    shared = common.message_type.add(name="Shared")
    _field(shared, "value", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    state = common.enum_type.add(name="State")
    state.value.add(name="STATE_UNSPECIFIED", number=0)
    state.value.add(name="STATE_READY", number=1)
    state.value.add(name="STATE_NEGATIVE", number=-1)

    widget_file = descriptor_pb2.FileDescriptorProto(
        name="acme/widget.proto",
        package="acme.widget",
        syntax="proto3",
        dependency=[common.name],
    )
    widget = widget_file.message_type.add(name="Widget")
    widget.oneof_decl.add(name="choice")
    _field(widget, "id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT64)
    _field(
        widget,
        "shared",
        2,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".acme.common.Shared",
    )
    _field(
        widget,
        "state",
        3,
        descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".acme.common.State",
    )
    _field(
        widget,
        "name",
        4,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        oneof_index=0,
    )
    _field(
        widget,
        "count",
        5,
        descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
        oneof_index=0,
    )
    entry = widget.nested_type.add(name="LabelsEntry")
    entry.options.map_entry = True
    _field(entry, "key", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    _field(entry, "value", 2, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    _field(
        widget,
        "labels",
        6,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".acme.widget.Widget.LabelsEntry",
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    _field(
        widget,
        "states",
        7,
        descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".acme.common.State",
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    nested = widget.nested_type.add(name="Nested")
    _field(nested, "value", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    kind = widget.enum_type.add(name="Kind")
    kind.value.add(name="KIND_UNSPECIFIED", number=0)
    kind.value.add(name="KIND_SPECIAL", number=1)
    _field(
        widget,
        "nested",
        8,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".acme.widget.Widget.Nested",
    )
    _field(
        widget,
        "kind",
        9,
        descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".acme.widget.Widget.Kind",
    )
    service = widget_file.service.add(name="WidgetService")
    service.method.add(
        name="GetWidget",
        input_type=".acme.widget.Widget",
        output_type=".acme.widget.Widget",
    )

    extension_file = descriptor_pb2.FileDescriptorProto(
        name="acme/extension.proto", package="acme.extension", syntax="proto2"
    )
    host = extension_file.message_type.add(name="Host")
    host.extension_range.add(start=100, end=200)
    host.field.add(name="hex_value", number=1, label=1, type=5, default_value="0x10")
    host.field.add(name="octal_value", number=2, label=1, type=5, default_value="010")
    host.field.add(name="positive_inf", number=3, label=1, type=1, default_value="inf")
    host.field.add(name="negative_inf", number=4, label=1, type=1, default_value="-inf")
    host.field.add(name="not_a_number", number=5, label=1, type=1, default_value="nan")
    host.extension.add(
        name="tag",
        number=101,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        extendee=".acme.extension.Host",
    )
    extension_file.extension.add(
        name="tag",
        number=100,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        extendee=".acme.extension.Host",
        default_value="default-tag",
    )
    mode = extension_file.enum_type.add(name="Mode")
    mode.value.add(name="MODE_UNSPECIFIED", number=0)
    mode.value.add(name="MODE_ON", number=1)
    extension_file.extension.add(
        name="mode",
        number=102,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".acme.extension.Mode",
        extendee=".acme.extension.Host",
        default_value="MODE_ON",
    )
    return plugin_pb2.CodeGeneratorRequest(
        proto_file=[common, widget_file, extension_file],
        file_to_generate=[common.name, widget_file.name, extension_file.name],
        parameter=f"package_prefix={namespace},partition={partition},jobs=2",
    )


def _materialize(root: Path, namespace: str, partition: str = "all") -> None:
    response = generate(_request(namespace, partition))
    assert not response.error
    for output in response.file:
        path = root / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)


def _operation_request(namespace: str) -> plugin_pb2.CodeGeneratorRequest:
    request = _request(namespace)
    operation_file = descriptor_pb2.FileDescriptorProto(
        name="nebius/common/v1/operation.proto",
        package="nebius.common.v1",
        syntax="proto3",
    )
    operation = operation_file.message_type.add(name="Operation")
    for number, name in enumerate(
        ("id", "description", "created_by", "resource_id"), start=1
    ):
        _field(operation, name, number, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    get_request = operation_file.message_type.add(name="GetOperationRequest")
    _field(get_request, "id", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    list_request = operation_file.message_type.add(name="ListOperationsRequest")
    _field(
        list_request,
        "parent_id",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    list_response = operation_file.message_type.add(name="ListOperationsResponse")
    _field(
        list_response,
        "operations",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".nebius.common.v1.Operation",
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    operation_service = operation_file.service.add(name="OperationService")
    operation_service.method.add(
        name="Get",
        input_type=".nebius.common.v1.GetOperationRequest",
        output_type=".nebius.common.v1.Operation",
    )
    operation_service.method.add(
        name="List",
        input_type=".nebius.common.v1.ListOperationsRequest",
        output_type=".nebius.common.v1.ListOperationsResponse",
    )
    widget_file = request.proto_file[1]
    widget_file.dependency.append(operation_file.name)
    widget_file.service[0].method.add(
        name="CreateWidget",
        input_type=".acme.widget.Widget",
        output_type=".nebius.common.v1.Operation",
    )
    request.proto_file.append(operation_file)
    request.file_to_generate.append(operation_file.name)
    return request


def _wkt_request(namespace: str) -> plugin_pb2.CodeGeneratorRequest:
    timestamp_file = descriptor_pb2.FileDescriptorProto.FromString(
        timestamp_pb2.DESCRIPTOR.serialized_pb
    )
    duration_file = descriptor_pb2.FileDescriptorProto.FromString(
        duration_pb2.DESCRIPTOR.serialized_pb
    )
    any_file = descriptor_pb2.FileDescriptorProto.FromString(
        any_pb2.DESCRIPTOR.serialized_pb
    )
    status_file = descriptor_pb2.FileDescriptorProto.FromString(
        status_pb2.DESCRIPTOR.serialized_pb
    )
    error_file = descriptor_pb2.FileDescriptorProto(
        name="nebius/common/v1/error.proto",
        package="nebius.common.v1",
        syntax="proto3",
    )
    service_error = error_file.message_type.add(name="ServiceError")
    _field(service_error, "value", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    alpha_error_file = descriptor_pb2.FileDescriptorProto(
        name="nebius/common/error/v1alpha1/error.proto",
        package="nebius.common.error.v1alpha1",
        syntax="proto3",
    )
    alpha_error = alpha_error_file.message_type.add(name="ServiceError")
    _field(alpha_error, "value", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    confusing_file = descriptor_pb2.FileDescriptorProto(
        name="confusing/errors.proto",
        package="confusing",
        syntax="proto3",
    )
    confusing_error = confusing_file.message_type.add(name="ServiceErrorLookalike")
    _field(
        confusing_error,
        "value",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    holder_file = descriptor_pb2.FileDescriptorProto(
        name="acme/wkt.proto",
        package="acme.wkt",
        syntax="proto3",
        dependency=[
            timestamp_file.name,
            duration_file.name,
            status_file.name,
            error_file.name,
            alpha_error_file.name,
            confusing_file.name,
        ],
    )
    holder = holder_file.message_type.add(name="Holder")
    holder.oneof_decl.add(name="time_choice")
    _field(
        holder,
        "created_at",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".google.protobuf.Timestamp",
    )
    _field(
        holder,
        "ttl",
        2,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".google.protobuf.Duration",
    )
    _field(
        holder,
        "moments",
        3,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".google.protobuf.Timestamp",
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    entry = holder.nested_type.add(name="ScheduleEntry")
    entry.options.map_entry = True
    _field(entry, "key", 1, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    _field(
        entry,
        "value",
        2,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".google.protobuf.Timestamp",
    )
    _field(
        holder,
        "schedule",
        4,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".acme.wkt.Holder.ScheduleEntry",
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    _field(
        holder,
        "selected_at",
        5,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".google.protobuf.Timestamp",
        oneof_index=0,
    )
    _field(
        holder,
        "request_status",
        6,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".google.rpc.Status",
    )
    _field(
        holder,
        "service_error",
        7,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".nebius.common.v1.ServiceError",
    )
    _field(
        holder,
        "alpha_service_error",
        8,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".nebius.common.error.v1alpha1.ServiceError",
    )
    _field(
        holder,
        "confusing_error",
        9,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".confusing.ServiceErrorLookalike",
    )
    return plugin_pb2.CodeGeneratorRequest(
        proto_file=[
            timestamp_file,
            duration_file,
            any_file,
            status_file,
            error_file,
            alpha_error_file,
            confusing_file,
            holder_file,
        ],
        file_to_generate=[holder_file.name],
        parameter=f"package_prefix={namespace}",
    )


def test_wkt_fields_are_python_views_over_authoritative_direct_values(
    tmp_path: Path,
) -> None:
    response = generate(_wkt_request("wkt"))
    assert not response.error
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)

    sys.path.insert(0, str(tmp_path))
    try:
        protobuf = importlib.import_module("wkt.google.protobuf")
        rpc = importlib.import_module("wkt.google.rpc")
        module = importlib.import_module("wkt.acme.wkt")
        timestamp = protobuf.Timestamp(seconds=-1, nanos=123)
        timestamp_payload = timestamp.SerializeToString() + b"\x18\x07"
        duration = protobuf.Duration(seconds=-1, nanos=-1)
        duration_payload = duration.SerializeToString()
        detail = protobuf.Any(
            type_url="type.example/unknown.Detail",
            value=b"opaque",
        )
        status_payload = (
            rpc.Status(
                code=StatusCode.INVALID_ARGUMENT.value[0],
                message="invalid",
                details=[detail],
            ).SerializeToString()
            + b"\x20\x07"
        )
        map_entry = _option_field(1, 2, b"key") + _option_field(2, 2, timestamp_payload)
        payload = b"".join(
            (
                _option_field(1, 2, timestamp_payload),
                _option_field(2, 2, duration_payload),
                _option_field(3, 2, timestamp_payload),
                _option_field(4, 2, map_entry),
                _option_field(5, 2, timestamp_payload),
                _option_field(6, 2, status_payload),
            )
        )
        holder = module.Holder.FromString(payload)
        expected = datetime(1969, 12, 31, 23, 59, 59, tzinfo=timezone.utc).astimezone()
        assert holder.created_at == expected
        assert holder.ttl == timedelta(seconds=-1)
        assert holder.moments == [expected]
        assert holder.schedule["key"] == expected
        assert holder.time_choice is not None
        assert holder.time_choice.value == expected
        assert holder.request_status is not None
        assert holder.request_status.code is StatusCode.INVALID_ARGUMENT
        assert holder.request_status.message == "invalid"
        assert holder.request_status.registry is module.REGISTRY
        assert len(holder.request_status.details) == 1
        assert (
            holder.request_status.details[0].type_url == "type.example/unknown.Detail"
        )
        assert holder.SerializeToString(deterministic=True) == payload

        original = holder.SerializeToString(deterministic=True)
        assert holder.schedule.get("missing") is None
        assert holder.schedule.get("missing", "fallback") == "fallback"
        assert "missing" not in holder.schedule
        assert holder.schedule.pop("missing", "fallback") == "fallback"
        assert holder.SerializeToString(deterministic=True) == original
        wanted = datetime(2024, 5, 6, tzinfo=timezone.utc)
        assert holder.schedule.setdefault("wanted", wanted) == wanted.astimezone()
        assert holder.schedule.setdefault("wanted", expected) == wanted.astimezone()
        assert holder.schedule.pop("wanted") == wanted.astimezone()
        with pytest.raises(KeyError):
            holder.schedule.pop("missing")

        later_timestamp_payload = (
            protobuf.Timestamp(seconds=2, nanos=456).SerializeToString() + b"\x20\x09"
        )
        moments_payload = _option_field(3, 2, timestamp_payload) + _option_field(
            3, 2, later_timestamp_payload
        )
        moments_holder = module.Holder.FromString(moments_payload)
        moments_holder.moments.reverse()
        assert moments_holder.SerializeToString(deterministic=True) == (
            _option_field(3, 2, later_timestamp_payload)
            + _option_field(3, 2, timestamp_payload)
        )

        with pytest.raises(ValueError, match="timestamp nanos"):
            module.Holder.FromString(
                _option_field(
                    1,
                    2,
                    protobuf.Timestamp(seconds=0, nanos=-1).SerializeToString(),
                )
            ).created_at
        with pytest.raises(ValueError, match="timestamp seconds"):
            module.Holder.FromString(
                _option_field(
                    1,
                    2,
                    protobuf.Timestamp(seconds=253_402_300_800).SerializeToString(),
                )
            ).created_at

        assigned_time = datetime(2020, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
        assigned = module.Holder(
            created_at=assigned_time,
            ttl=timedelta(microseconds=-1),
            moments=[assigned_time],
            schedule={"key": assigned_time},
            selected_at=assigned_time,
            request_status=holder.request_status,
        )
        assert assigned.created_at == assigned_time.astimezone()
        assert assigned.ttl == timedelta(microseconds=-1)
        assert assigned.moments[0] == assigned_time.astimezone()
        assert assigned.schedule["key"] == assigned_time.astimezone()
        assert assigned.request_status is not None
        assert assigned.request_status.registry is module.REGISTRY
        assert _option_field(6, 2, status_payload) in assigned.SerializeToString(
            deterministic=True
        )

        def full_field_mask(holder, name: str) -> Mask | None:
            return holder.get_full_update_reset_mask().field_parts.get(FieldKey(name))

        empty_holder = module.Holder()
        for name in (
            "created_at",
            "ttl",
            "moments",
            "schedule",
            "selected_at",
            "request_status",
        ):
            assert full_field_mask(empty_holder, name) == Mask()

        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        assert full_field_mask(
            module.Holder(created_at=epoch), "created_at"
        ).marshal() == ("nanos,seconds")
        assert (
            full_field_mask(
                module.Holder(created_at=epoch + timedelta(seconds=1)), "created_at"
            ).marshal()
            == "nanos"
        )
        assert (
            full_field_mask(
                module.Holder(created_at=epoch + timedelta(seconds=1, microseconds=1)),
                "created_at",
            )
            == Mask()
        )

        assert full_field_mask(module.Holder(moments=[]), "moments") == Mask()
        moments_mask = full_field_mask(
            module.Holder(moments=[epoch, epoch + timedelta(seconds=1)]),
            "moments",
        )
        assert moments_mask is not None and moments_mask.any is not None
        assert moments_mask.any.marshal() == "nanos,seconds"

        assert full_field_mask(module.Holder(schedule={}), "schedule") == Mask()
        schedule_mask = full_field_mask(
            module.Holder(schedule={"epoch": epoch}), "schedule"
        )
        assert schedule_mask is not None and schedule_mask.any is not None
        assert schedule_mask.any.marshal() == "nanos,seconds"

        assert full_field_mask(assigned, "request_status").marshal() == "details.*"
        reparsed = module.Holder.FromString(assigned.SerializeToString())
        assert reparsed.created_at == assigned_time.astimezone()
        with pytest.raises(TypeError, match="timestamp field"):
            module.Holder(created_at=protobuf.Duration(seconds=1))
        with pytest.raises(TypeError, match="duration field"):
            module.Holder(ttl=protobuf.Timestamp(seconds=1))

        usage = tmp_path / "wkt_typing.py"
        usage.write_text("""\
from collections.abc import MutableMapping, MutableSequence
from datetime import datetime, timedelta

from nebius.aio.request_status import RequestStatus
from wkt.acme.wkt import Holder
from wkt.google.protobuf import Timestamp


def check(holder: Holder, raw: Timestamp, value: datetime) -> None:
    created: datetime | None = holder.created_at
    ttl: timedelta | None = holder.ttl
    moments: MutableSequence[datetime] = holder.moments
    schedule: MutableMapping[str, datetime] = holder.schedule
    status: RequestStatus | None = holder.request_status
    holder.created_at = raw
    Holder(created_at=value, moments=[raw, value], schedule={"x": raw})
""")
        environment = os.environ.copy()
        environment["MYPYPATH"] = os.pathsep.join(
            (str(tmp_path), str(Path(__file__).parents[2] / "src"))
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--strict",
                "--no-incremental",
                str(usage),
            ],
            cwd=Path(__file__).parents[2],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        sys.path.remove(str(tmp_path))


def test_status_views_retain_and_retarget_namespace_registries(tmp_path: Path) -> None:
    for namespace in ("status_public", "status_alternate"):
        response = generate(_wkt_request(namespace))
        assert not response.error
        for output in response.file:
            path = tmp_path / output.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output.content)

    sys.path.insert(0, str(tmp_path))
    try:
        public = importlib.import_module("status_public.acme.wkt")
        public_common = importlib.import_module("status_public.nebius.common.v1")
        public_alpha = importlib.import_module(
            "status_public.nebius.common.error.v1alpha1"
        )
        public_confusing = importlib.import_module("status_public.confusing")
        alternate = importlib.import_module("status_alternate.acme.wkt")
        public_error = public_common.ServiceError(value="original")
        alpha_error = public_alpha.ServiceError(value="alpha")
        confusing_error = public_confusing.ServiceErrorLookalike(value="opaque")
        details = [
            public.REGISTRY.pack_any(public_error),
            public.REGISTRY.pack_any(alpha_error),
            public.REGISTRY.pack_any(confusing_error),
        ]
        status_type = public.REGISTRY.message_class("google.rpc.Status")
        raw_status = (
            status_type(
                code=123,
                message="unknown code",
                details=details,
            ).SerializeToString()
            + b"\x20\x07"
        )
        public_status = public.Holder.FromString(
            _option_field(6, 2, raw_status)
        ).request_status
        assert public_status is not None
        assert public_status.code is StatusCode.UNKNOWN
        assert public_status.registry is public.REGISTRY
        assert len(public_status.service_errors) == 2
        assert len(public_status.details) == 1
        assert public_status.details[0].type_url.endswith(
            "/confusing.ServiceErrorLookalike"
        )

        alternate_holder = alternate.Holder(request_status=public_status)
        assert alternate_holder.SerializeToString(deterministic=True) == _option_field(
            6, 2, raw_status
        )
        assert alternate_holder.request_status is not None
        assert alternate_holder.request_status.registry is alternate.REGISTRY
        assert len(alternate_holder.request_status.service_errors) == 2
        assert (
            type(alternate_holder.request_status.service_errors[0]).__REGISTRY__
            is alternate.REGISTRY
        )

        public_status.service_errors[0].value = "changed"
        public_status.service_errors[1].value = "changed alpha"
        changed_holder = alternate.Holder(request_status=public_status)
        assert changed_holder.request_status is not None
        assert changed_holder.request_status.service_errors[0].value == "changed"
        assert changed_holder.request_status.service_errors[1].value == "changed alpha"
        assert (
            type(changed_holder.request_status.service_errors[0]).__REGISTRY__
            is alternate.REGISTRY
        )
        changed_raw = public_status.to_rpc_status(registry=alternate.REGISTRY)
        assert changed_raw.code == 123
        assert b"\x20\x07" in changed_raw.SerializeToString(deterministic=True)

        from nebius.aio.request import Request
        from nebius.aio.route import Route

        request = Request(
            channel=object(),  # type: ignore[arg-type]
            service="acme.WktService",
            method="Get",
            request=alternate.Holder(),
            result_pb2_class=public.Holder,
            route=Route(
                service="acme.WktService",
                method="Get",
                registry=public.REGISTRY,
            ),
        )
        assert request._registry is public.REGISTRY

        class NoRichError:
            def initial_metadata(self) -> list[tuple[str, str]]:
                return []

            def trailing_metadata(self) -> list[tuple[str, str]]:
                return []

            def code(self) -> StatusCode:
                return StatusCode.UNAVAILABLE

            def details(self) -> str:
                return "unavailable"

            def debug_error_string(self) -> str:
                return ""

        from nebius.aio.service_error import RequestError as ServiceRequestError

        with pytest.raises(ServiceRequestError) as captured:
            request._raise_request_error(NoRichError())  # type: ignore[arg-type]
        assert captured.value.status.registry is public.REGISTRY
        assert (
            type(captured.value.status.to_rpc_status()).__REGISTRY__ is public.REGISTRY
        )

        class FakeCall:
            def __init__(self, payload: bytes, code: StatusCode) -> None:
                self.payload = payload
                self.status_code = code

            def trailing_metadata(self) -> list[tuple[str, bytes]]:
                return [("grpc-status-details-bin", self.payload)]

            def code(self) -> StatusCode:
                return self.status_code

            def details(self) -> str:
                return "missing"

        call = FakeCall(
            status_type(
                code=StatusCode.NOT_FOUND.value[0], message="missing"
            ).SerializeToString(),
            StatusCode.NOT_FOUND,
        )
        decoded = rpc_status_from_call(call, registry=public.REGISTRY)
        assert type(decoded) is status_type
        call.status_code = StatusCode.INVALID_ARGUMENT
        with pytest.raises(ValueError, match="code"):
            rpc_status_from_call(call, registry=public.REGISTRY)
    finally:
        sys.path.remove(str(tmp_path))


def test_operation_outputs_use_direct_registry_owned_wrappers(tmp_path: Path) -> None:
    response = generate(_operation_request("operations"))
    assert not response.error
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)

    sys.path.insert(0, str(tmp_path))
    try:
        widget = importlib.import_module("operations.acme.widget")
        common = importlib.import_module("operations.nebius.common.v1")
        from nebius.aio.client import ClientWithOperations
        from nebius.aio.operation import Operation
        from nebius.aio.operation_service import OperationServiceTransportStub
        from nebius.aio.service_descriptor import from_stub_class

        assert issubclass(widget.WidgetServiceClient, ClientWithOperations)
        assert not issubclass(common.OperationServiceClient, ClientWithOperations)
        assert widget.WidgetServiceClient.__operation_type__ is common.Operation
        assert (
            widget.WidgetServiceClient.__operation_service_class__
            is common.OperationServiceClient
        )

        class Channel:
            def parent_id(self) -> None:
                return None

        channel = Channel()
        client = widget.WidgetServiceClient(channel)  # type: ignore[arg-type]
        pending = client.create_widget(widget.Widget())
        raw = common.Operation(id="operation-1", resource_id="resource-1")
        wrapped = pending._result_wrapper(  # type: ignore[misc]
            "acme.widget.WidgetService.CreateWidget",
            channel,
            raw,
        )
        assert isinstance(wrapped, Operation)
        assert wrapped.raw() is raw
        assert wrapped.id == "operation-1"
        assert type(wrapped._operation).__REGISTRY__ is common.REGISTRY
        assert client.operation_service() is client.operation_service()
        assert isinstance(client.operation_service(), common.OperationServiceClient)

        calls: list[tuple[str, object, object]] = []

        class Transport:
            def unary_unary(
                self,
                path: str,
                *,
                request_serializer: object,
                response_deserializer: object,
            ) -> str:
                calls.append((path, request_serializer, response_deserializer))
                return path

        transport_stub = OperationServiceTransportStub(
            Transport(),  # type: ignore[arg-type]
            common.REGISTRY,
        )
        assert transport_stub.Get == "/nebius.common.v1.OperationService/Get"
        assert transport_stub.List == "/nebius.common.v1.OperationService/List"
        assert calls[0][1](common.GetOperationRequest(id="x")) != b""  # type: ignore[operator]
        assert calls[0][2](raw.SerializeToString()).id == "operation-1"  # type: ignore[operator]
        assert from_stub_class(widget.WidgetServiceClient) == (
            "acme.widget.WidgetService"
        )
    finally:
        sys.path.remove(str(tmp_path))


def test_partition_modes_emit_byte_identical_trees() -> None:
    outputs: list[list[tuple[str, str]]] = []
    for partition in ("all", "package", "directory"):
        response = generate(_request("generated", partition))
        assert not response.error
        outputs.append([(item.name, item.content) for item in response.file])
    assert outputs[0] == outputs[1] == outputs[2]
    names = [name for name, _ in outputs[0]]
    source = "\n".join(content for _, content in outputs[0])
    assert not any(name.endswith(("_pb2.py", "_pb2_grpc.py")) for name in names)
    assert "__pb2_message__" not in source
    assert "descriptor_pool" not in source


def test_split_package_links_one_relative_import_per_target() -> None:
    request = _request("relative_edges")
    extra = descriptor_pb2.FileDescriptorProto(
        name="alternate/extra.proto", package="acme.widget", syntax="proto3"
    )
    extra.dependency.append("acme/common.proto")
    holder = extra.message_type.add(name="Extra")
    _field(
        holder,
        "shared",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".acme.common.Shared",
    )
    request.proto_file.append(extra)
    request.file_to_generate.append(extra.name)

    response = generate(request)

    assert not response.error
    source = _implementation_source(response, "relative_edges/acme/widget")
    tree = ast.parse(source)
    absolute_edges = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        and any(alias.name.startswith("relative_edges.") for alias in node.names)
    ]
    relative_common_edges = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.level > 0
        and any(alias.name == "common" for alias in node.names)
    ]
    assert not absolute_edges
    assert len(relative_common_edges) == 1


def test_large_package_shards_are_lazy_and_keep_public_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _request("sharded_edges")
    extra = descriptor_pb2.FileDescriptorProto(
        name="alternate/extra.proto", package="acme.widget", syntax="proto3"
    )
    for name in ("Extra", "getattr", "globals", "isinstance", "sorted", "type"):
        extra.message_type.add(name=name)
    request.proto_file.append(extra)
    request.file_to_generate.append(extra.name)
    monkeypatch.setattr(emitter, "_SHARD_LINE_LIMIT", 1)

    response = generate(request)

    assert not response.error
    names = {output.name for output in response.file}
    assert "sharded_edges/acme/widget/__init__.py" in names
    assert any(name.endswith("/_impl_000.py") for name in names)
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)

    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("sharded_edges.acme.widget")
        assert "Widget" not in vars(module)
        assert "Extra" not in vars(module)

        widget_type = module.Widget
        assert widget_type.__module__ == "sharded_edges.acme.widget"
        assert "Widget" in vars(module)
        assert "Extra" not in vars(module)
        restored_type = pickle.loads(pickle.dumps(widget_type.Nested))  # noqa: S301
        assert restored_type is widget_type.Nested

        extra_type = module.Extra
        assert extra_type.__module__ == "sharded_edges.acme.widget"
        reparsed = extra_type.FromString(extra_type().SerializeToString())
        assert reparsed.__class__ is extra_type
        for builtin_name in ("getattr", "globals", "isinstance", "sorted", "type"):
            exported_name = (
                builtin_name + "_"
                if keyword.iskeyword(builtin_name)
                or keyword.issoftkeyword(builtin_name)
                else builtin_name
            )
            assert (
                getattr(module, exported_name).__module__ == "sharded_edges.acme.widget"
            )
    finally:
        sys.path.remove(str(tmp_path))


def test_small_packages_are_lazy_and_own_registry_fragments() -> None:
    response = generate(_request("fragmented"))

    assert not response.error
    names = {output.name for output in response.file}
    assert "fragmented/acme/widget/_impl_000.py" in names
    assert "fragmented/acme/widget/_registry_fragment.py" in names
    facade = next(
        output.content
        for output in response.file
        if output.name == "fragmented/acme/widget/__init__.py"
    )
    fragment = next(
        output.content
        for output in response.file
        if output.name == "fragmented/acme/widget/_registry_fragment.py"
    )
    registry = next(
        output.content
        for output in response.file
        if output.name == "fragmented/_registry.py"
    )
    assert "from ._impl_000" in facade
    assert "from fragmented._registry" not in facade
    assert "module=__package__" in fragment
    assert "RegistryFragment(" in fragment
    assert "Registry.from_fragments" in registry


@pytest.mark.parametrize(
    "name",
    (
        "_impl_000",
        "_NEBIUS_EXPORT_SHARDS",
        "_NEBIUS_SHARD_NAMES",
        "_nebius_import_module",
        "_nebius_module_getattr",
        "_NebiusGetattr",
        "__getattr__",
        "__dir__",
    ),
)
def test_lazy_shard_helpers_are_reserved(name: str) -> None:
    request = _request("sharded_collision")
    request.proto_file[1].message_type.add(name=name)

    response = generate(request)

    assert "shadows generated import" in response.error


@pytest.mark.parametrize("kind", ("message", "enum"))
@pytest.mark.parametrize("name", ("_NEBIUS_UNSET", "_NebiusOneOf", "_NebiusProperty"))
def test_message_class_runtime_names_are_reserved(name: str, kind: str) -> None:
    request = _request("class_collision")
    widget = request.proto_file[1].message_type[0]
    if kind == "message":
        widget.nested_type.add(name=name)
    else:
        nested = widget.enum_type.add(name=name)
        nested.value.add(name="VALUE_UNSPECIFIED", number=0)

    response = generate(request)

    assert "Python member collision" in response.error


def test_nested_attachments_do_not_depend_on_child_order(tmp_path: Path) -> None:
    request = _request("nested_order")
    outer = request.proto_file[1].message_type.add(name="Outer")
    outer.nested_type.add(name="Outer__A")
    outer.nested_type.add(name="A")
    for index, enum_name in enumerate(("Outer__Kind", "Kind")):
        nested_enum = outer.enum_type.add(name=enum_name)
        nested_enum.value.add(name=f"VALUE_{index}_UNSPECIFIED", number=0)

    response = generate(request)

    assert not response.error
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)
    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("nested_order.acme.widget")
        assert module.Outer.Outer__A is not module.Outer.A
        assert module.Outer.Outer__A.__qualname__ == "Outer.Outer__A"
        assert module.Outer.A.__qualname__ == "Outer.A"
        assert module.Outer.Outer__Kind is not module.Outer.Kind
        assert module.Outer.Outer__Kind.__qualname__ == "Outer.Outer__Kind"
        assert module.Outer.Kind.__qualname__ == "Outer.Kind"
    finally:
        sys.path.remove(str(tmp_path))


def test_runtime_closure_excludes_option_only_dependency() -> None:
    request = _request("closure")
    metadata = descriptor_pb2.FileDescriptorProto(
        name="metadata/options.proto", package="metadata.options", syntax="proto3"
    )
    metadata.message_type.add(name="Rule")
    request.proto_file.append(metadata)
    request.proto_file[1].dependency.append(metadata.name)
    request.file_to_generate.remove(request.proto_file[0].name)

    response = generate(request)

    assert not response.error
    names = {file.name for file in response.file}
    assert "closure/acme/common/__init__.py" in names
    assert "closure/metadata/options/__init__.py" not in names
    metadata_fragment = next(
        file.content
        for file in response.file
        if file.name == "closure/_registry_fragment.py"
    )
    assert "metadata/options.proto" in metadata_fragment


def test_runtime_closure_is_declaration_granular() -> None:
    request = _request("closure")
    dependency = descriptor_pb2.FileDescriptorProto(
        name="dependency/mixed.proto", package="dependency", syntax="proto3"
    )
    dependency.message_type.add(name="Used")
    unused = dependency.message_type.add(name="Unused")
    _field(
        unused,
        "other",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".other.Other",
    )
    other = descriptor_pb2.FileDescriptorProto(
        name="other/other.proto", package="other", syntax="proto3"
    )
    other.message_type.add(name="Other")
    dependency.dependency.append(other.name)
    request.proto_file.extend((dependency, other))
    request.proto_file[1].dependency.append(dependency.name)
    _field(
        request.proto_file[1].message_type[0],
        "used",
        10,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".dependency.Used",
    )

    response = generate(request)

    assert not response.error
    names = {file.name for file in response.file}
    dependency_source = _implementation_source(response, "closure/dependency")
    assert "class Used(Message):" in dependency_source
    assert "class Unused(Message):" not in dependency_source
    assert "closure/other/__init__.py" not in names


def test_nested_extension_activates_external_extendee() -> None:
    host_file = descriptor_pb2.FileDescriptorProto(
        name="dependency/host.proto", package="dependency", syntax="proto2"
    )
    host = host_file.message_type.add(name="Host")
    host.extension_range.add(start=100, end=200)
    root_file = descriptor_pb2.FileDescriptorProto(
        name="root/extensions.proto",
        package="root",
        syntax="proto2",
        dependency=[host_file.name],
    )
    scope = root_file.message_type.add(name="Scope")
    scope.extension.add(
        name="tag",
        number=100,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        extendee=".dependency.Host",
    )
    request = plugin_pb2.CodeGeneratorRequest(
        proto_file=[host_file, root_file],
        file_to_generate=[root_file.name],
        parameter="package_prefix=nested_extension",
    )

    response = generate(request)

    assert not response.error
    names = {file.name for file in response.file}
    assert "nested_extension/dependency/__init__.py" in names


def test_fragment_verifier_rejects_owner_and_key_tampering(tmp_path: Path) -> None:
    request = _request("attested", "directory")
    raw = request.SerializeToString(deterministic=True)
    manifest = tmp_path / "request.bin"
    output = tmp_path / "src"
    manifest.write_bytes(raw)
    coordinate(manifest, output)
    graph_request = parse_request(raw)
    graph = Graph(graph_request, Options.parse(graph_request.parameter))
    batches = coordinator._batches(graph)
    semantic = coordinator._semantic_digest()
    fragments = sorted((tmp_path / "fragments").iterdir())
    original_payloads = [json.loads(path.read_text()) for path in fragments]
    attestations = [
        coordinator.FragmentAttestation(
            path,
            payload["key"],
            payload["content_hash"],
            payload["owner"],
            tuple(payload["files"]),
        )
        for path, payload in zip(fragments, original_payloads, strict=True)
    ]
    payload = original_payloads[0]
    invocation = payload["invocation"]
    original_owner = payload["owner"]

    payload["owner"] = "WRONG"
    fragments[0].write_text(json.dumps(payload))
    with pytest.raises(GeneratorError, match="attestation mismatch"):
        coordinator._verify_fragments(
            attestations, graph, invocation, semantic, batches
        )

    payload["owner"] = original_owner
    payload["key"] = "0" * 64
    tampered = fragments[0].with_name("0" * 64 + ".json")
    fragments[0].rename(tampered)
    tampered.write_text(json.dumps(payload))
    tampered_attestation = coordinator.FragmentAttestation(
        tampered,
        attestations[0].key,
        attestations[0].content_hash,
        attestations[0].owner,
        attestations[0].files,
    )
    with pytest.raises(GeneratorError, match="attestation mismatch"):
        coordinator._verify_fragments(
            [tampered_attestation, *attestations[1:]],
            graph,
            invocation,
            semantic,
            batches,
        )


def test_persistent_fragment_cache_rejects_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv(
        "NEBIUS_GENERATOR_CACHE_KEY_FILE", str(tmp_path / "state" / "cache.key")
    )
    request = _request("cached", "package")
    request.parameter += f",cache_dir={cache}"
    manifest = tmp_path / "request.bin"
    manifest.write_bytes(request.SerializeToString(deterministic=True))

    coordinate(manifest, tmp_path / "first" / "src")
    objects = sorted(cache.rglob("*.json"))
    assert objects
    objects[0].write_text("not json")

    coordinate(manifest, tmp_path / "second" / "src")

    repaired = json.loads(objects[0].read_text())
    assert repaired["content_hash"] == coordinator._content_hash(repaired)

    semantic_object = next(
        path for path in objects if "Field('value', 'value', 1," in path.read_text()
    )
    tampered = json.loads(semantic_object.read_text())
    source_file = next(iter(tampered["ir"]))
    package = next(iter(tampered["ir"][source_file]))
    tampered["ir"][source_file][package] = tampered["ir"][source_file][package].replace(
        "Field('value', 'value', 1,", "Field('value', 'value', 2,"
    )
    tampered["content_hash"] = coordinator._content_hash(tampered)
    renamed_tamper = semantic_object.with_name(tampered["content_hash"] + ".json")
    semantic_object.rename(renamed_tamper)
    renamed_tamper.write_text(json.dumps(tampered))
    pointer = semantic_object.parent / "current"
    pointer_value = json.loads(pointer.read_text())
    pointer_value["content_hash"] = tampered["content_hash"]
    pointer.write_text(json.dumps(pointer_value))

    coordinate(manifest, tmp_path / "third" / "src")

    repaired_semantic = json.loads(semantic_object.read_text())
    repaired_source = repaired_semantic["ir"][source_file][package]
    assert "Field('value', 'value', 1," in repaired_source


def test_persistent_cache_allows_concurrent_identical_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv(
        "NEBIUS_GENERATOR_CACHE_KEY_FILE", str(tmp_path / "state" / "cache.key")
    )
    request = _request("concurrent_cache", "package")
    request.parameter += f",cache_dir={cache}"
    manifest = tmp_path / "request.bin"
    manifest.write_bytes(request.SerializeToString(deterministic=True))

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [
            executor.submit(coordinate, manifest, tmp_path / f"run-{index}" / "src")
            for index in range(8)
        ]
        for future in futures:
            future.result()

    assert all(
        json.loads(path.read_text())["content_hash"]
        == coordinator._content_hash(json.loads(path.read_text()))
        for path in cache.rglob("*.json")
    )


def test_cache_signing_key_cold_initialization_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key_file = tmp_path / "state" / "cache.key"
    monkeypatch.setenv("NEBIUS_GENERATOR_CACHE_KEY_FILE", str(key_file))

    with ThreadPoolExecutor(max_workers=64) as executor:
        keys = list(executor.map(lambda _: coordinator._cache_signing_key(), range(64)))

    assert len(set(keys)) == 1
    assert keys[0] == key_file.read_bytes()
    assert len(keys[0]) == 32


def test_persistent_cache_hit_does_not_reanalyze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv(
        "NEBIUS_GENERATOR_CACHE_KEY_FILE", str(tmp_path / "state" / "cache.key")
    )
    request = _request("cache_hit", "package")
    request.parameter += f",cache_dir={cache}"
    manifest = tmp_path / "request.bin"
    manifest.write_bytes(request.SerializeToString(deterministic=True))
    coordinate(manifest, tmp_path / "first" / "src")

    def fail_analysis(*args, **kwargs):
        raise AssertionError("cache hit re-ran analysis")

    monkeypatch.setattr(coordinator, "_analyze_files", fail_analysis)
    coordinate(manifest, tmp_path / "second" / "src")


def test_linker_rechecks_attestation_after_verification(tmp_path: Path) -> None:
    request = _request("toctou", "package")
    manifest = tmp_path / "request.bin"
    output = tmp_path / "src"
    manifest.write_bytes(request.SerializeToString(deterministic=True))
    coordinate(manifest, output)
    fragment = next((tmp_path / "fragments").iterdir())
    payload = json.loads(fragment.read_text())
    attested_hash = payload["content_hash"]
    source_file = next(iter(payload["ir"]))
    package = next(iter(payload["ir"][source_file]))
    payload["ir"][source_file][package] += "\n# changed after verification\n"
    payload["content_hash"] = coordinator._content_hash(payload)
    fragment.write_text(json.dumps(payload))

    with pytest.raises(GeneratorError, match="changed after verification"):
        coordinator._load_attested_payload(fragment, attested_hash)


def test_worker_batch_view_contains_only_owned_models_and_type_signatures() -> None:
    request = _request("batch")
    graph_request = parse_request(request.SerializeToString(deterministic=True))
    graph = Graph(graph_request, Options.parse(graph_request.parameter))

    view = graph.batch_view(frozenset({"acme/widget.proto"}))

    assert set(view.files) == {"acme/widget.proto"}
    assert "acme.widget.Widget" in view.messages
    assert "acme.common.Shared" in view.messages
    assert "acme.extension.Host" not in view.messages
    assert set(view.services) == {"acme.widget.WidgetService"}
    assert not view.extensions


def test_coordinator_partition_modes_emit_byte_identical_trees(tmp_path: Path) -> None:
    def request_for(partition: str):
        request = _request("coordinated", partition)
        extra = descriptor_pb2.FileDescriptorProto(
            name="alternate/extra.proto", package="acme.widget", syntax="proto3"
        )
        extra.message_type.add(name="Extra")
        request.proto_file.append(extra)
        request.file_to_generate.append(extra.name)
        return request

    expected = generate(request_for("all"))
    assert not expected.error
    expected_files = {item.name: item.content.encode() for item in expected.file}
    for partition in ("all", "package", "directory"):
        request = request_for(partition)
        manifest = tmp_path / f"{partition}.bin"
        output = tmp_path / partition
        manifest.write_bytes(request.SerializeToString(deterministic=True))
        coordinate(manifest, output)
        actual_files = {
            str(path.relative_to(output)): path.read_bytes()
            for path in output.rglob("*.py")
        }
        assert actual_files == expected_files
    fragments = [
        json.loads(path.read_text()) for path in (tmp_path / "fragments").iterdir()
    ]
    owners = {
        fragment["owner"]
        for fragment in fragments
        if any(
            symbol.startswith("acme.widget.")
            for symbol in fragment["symbols"]["messages"]
        )
    }
    assert owners == {"acme", "alternate"}


def test_capture_plugin_writes_exact_request_outside_response(tmp_path: Path) -> None:
    request = _request("captured").SerializeToString(deterministic=True)
    manifest = tmp_path / "request.bin"
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "src")))
    environment["NEBIUS_GENERATOR_MANIFEST"] = str(manifest)

    completed = subprocess.run(
        [sys.executable, "-m", "nebius_generator.capture"],
        cwd=root,
        env=environment,
        input=request,
        capture_output=True,
        check=True,
    )

    response = plugin_pb2.CodeGeneratorResponse.FromString(completed.stdout)
    assert not response.error
    assert not response.file
    assert manifest.read_bytes() == request


def test_plugin_io_uses_committed_sdk_api() -> None:
    request = _request("committed")
    root = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "src")))

    completed = subprocess.run(
        [sys.executable, "-m", "nebius_generator.main"],
        cwd=root,
        env=environment,
        input=request.SerializeToString(deterministic=True),
        capture_output=True,
        check=True,
    )

    response = plugin_pb2.CodeGeneratorResponse.FromString(completed.stdout)
    assert not response.error
    assert response.supported_features & response.FEATURE_PROTO3_OPTIONAL
    assert any(item.name.endswith("/_registry.py") for item in response.file)
    assert parse_request(request.SerializeToString()).__class__.__module__ == (
        "nebius.api.google.protobuf.compiler"
    )


@pytest.mark.asyncio
async def test_all_streaming_rpc_shapes_use_native_transport(tmp_path: Path) -> None:
    request = _request("streaming")
    service = request.proto_file[1].service[0]
    service.method.add(
        name="WatchWidgets",
        input_type=".acme.widget.Widget",
        output_type=".acme.widget.Widget",
        server_streaming=True,
    )
    service.method.add(
        name="UploadWidgets",
        input_type=".acme.widget.Widget",
        output_type=".acme.widget.Widget",
        client_streaming=True,
    )
    service.method.add(
        name="ChatWidgets",
        input_type=".acme.widget.Widget",
        output_type=".acme.widget.Widget",
        client_streaming=True,
        server_streaming=True,
    )
    response = generate(request)
    assert not response.error
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)

    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("streaming.acme.widget")
        message = module.Widget(id=7)
        opened: list[tuple[str, str]] = []
        returned: list[object] = []

        class Call:
            def __init__(self, response):
                self.response = response
                self.writes = []

            def __await__(self):
                async def result():
                    return self.response

                return result().__await__()

            def __aiter__(self):
                async def responses():
                    yield self.response

                return responses()

            async def write(self, value):
                self.writes.append(value)

            async def done_writing(self):
                return None

            def cancel(self):
                return True

        class Transport:
            def _multi(self, shape, path, serializer, deserializer):
                opened.append((shape, path))

                def invoke(*args, **kwargs):
                    return Call(deserializer(serializer(message)))

                return invoke

            def unary_stream(self, path, serializer, deserializer):
                return self._multi("unary_stream", path, serializer, deserializer)

            def stream_unary(self, path, serializer, deserializer):
                return self._multi("stream_unary", path, serializer, deserializer)

            def stream_stream(self, path, serializer, deserializer):
                return self._multi("stream_stream", path, serializer, deserializer)

        class Address:
            channel = Transport()

        class Channel:
            def get_channel_by_route(self, route):
                return Address()

            def return_channel(self, channel):
                returned.append(channel)

            def discard_channel(self, channel):
                returned.append(channel)

        client = module.WidgetServiceClient(Channel())
        watched = [item async for item in client.watch_widgets(message)]
        assert watched[0].id == 7

        upload = client.upload_widgets()
        await upload.write(message)
        await upload.done_writing()
        assert (await upload).id == 7

        chat = client.chat_widgets()
        await chat.write(message)
        await chat.done_writing()
        chatted = [item async for item in chat]
        assert chatted[0].id == 7

        assert [shape for shape, _ in opened] == [
            "unary_stream",
            "stream_unary",
            "stream_stream",
        ]
        assert all(path.startswith("/acme.widget.WidgetService/") for _, path in opened)
        assert len(returned) == 3
    finally:
        sys.path.remove(str(tmp_path))


def test_generated_namespaces_are_direct_and_isolated(tmp_path: Path) -> None:
    _materialize(tmp_path, "ns_one")
    _materialize(tmp_path, "ns_two", "directory")
    sys.path.insert(0, str(tmp_path))
    try:
        one_common = importlib.import_module("ns_one.acme.common")
        one_widget = importlib.import_module("ns_one.acme.widget")
        two_widget = importlib.import_module("ns_two.acme.widget")
        one_extension = importlib.import_module("ns_one.acme.extension")

        original = one_widget.Widget(
            id=2**61,
            shared=one_common.Shared(value="owned"),
            state=one_common.State.STATE_READY,
            name="selected",
            labels={"zone": 3},
            states=[0, 1],
            nested=one_widget.Widget.Nested(value="nested"),
            kind=one_widget.Widget.Kind.KIND_SPECIAL,
        )
        wire = original.SerializeToString(deterministic=True) + b"\x98\x06\x07"
        decoded = two_widget.Widget.FromString(wire)
        assert decoded.id == 2**61
        assert decoded.shared.value == "owned"
        two_common = importlib.import_module("ns_two.acme.common")
        assert decoded.state is two_common.State.STATE_READY
        assert decoded.states[1] is two_common.State.STATE_READY
        assert list(decoded.states) == [0, 1]
        assert one_common.State.STATE_NEGATIVE.value == -1
        assert decoded.nested.value == "nested"
        assert decoded.kind is two_widget.Widget.Kind.KIND_SPECIAL
        assert one_widget.Widget.Nested.__qualname__ == "Widget.Nested"
        assert one_widget.Widget.Kind.__qualname__ == "Widget.Kind"
        assert one_widget.Widget.__PY_TO_PB2__["Nested"] == "Nested"
        assert one_widget.Widget.__PY_TO_PB2__["Kind"] == "Kind"
        assert "Nested" in dir(original)
        assert "Kind" in dir(original)
        assert decoded.WhichOneof("choice") == "name"
        assert original.choice is not None
        assert original.choice.field == "name"
        assert original.choice.name == "choice"
        assert original.choice.value == "selected"
        assert dict(decoded.labels) == {"zone": 3}
        assert b"\x98\x06\x07" in decoded.SerializeToString(deterministic=True)
        assert type(original) is not type(decoded)
        assert original.get_descriptor() is not decoded.get_descriptor()
        assert one_widget.WidgetServiceClient.__service_name__ == (
            "acme.widget.WidgetService"
        )
        assert (
            one_widget.WidgetServiceClient.get_descriptor()
            .methods_by_name["GetWidget"]
            .output_type.full_name
            == "acme.widget.Widget"
        )

        host = one_extension.Host()
        assert host.hex_value == 16
        assert host.octal_value == 8
        assert host.positive_inf == float("inf")
        assert host.negative_inf == float("-inf")
        assert host.not_a_number != host.not_a_number
        assert not host.HasField("hex_value")
        assert host.get_extension(one_extension.tag) == "default-tag"
        assert host.get_extension(one_extension.mode) is one_extension.Mode.MODE_ON
        host.set_extension(one_extension.tag, "typed")
        assert host.get_extension(one_extension.tag) == "typed"
        assert (
            one_extension.Host.FromString(host.SerializeToString()).get_extension(
                one_extension.tag
            )
            == "typed"
        )
        host.set_extension(one_extension.Host.tag, "scoped")
        decoded_host = one_extension.Host.FromString(host.SerializeToString())
        assert decoded_host.get_extension(one_extension.Host.tag) == "scoped"

        calls: list[str] = []

        class Transport:
            def unary_unary(self, path, serializer, deserializer):
                calls.append(path)
                assert serializer(original) == original.SerializeToString()
                assert deserializer(original.SerializeToString()).id == original.id

                def call(*args, **kwargs):
                    return object()

                return call

        class Address:
            channel = Transport()

        class Channel:
            def parent_id(self):
                return None

            def get_channel_by_method(self, method):
                return Address()

        pending = one_widget.WidgetServiceClient(Channel()).get_widget(original)
        pending._send(None)
        assert calls == ["/acme.widget.WidgetService/GetWidget"]
    finally:
        sys.path.remove(str(tmp_path))


def test_generated_inline_types_pass_mypy(tmp_path: Path) -> None:
    request = _request("typed")
    service = request.proto_file[1].service[0]
    service.method.add(
        name="WatchWidgets",
        input_type=".acme.widget.Widget",
        output_type=".acme.widget.Widget",
        server_streaming=True,
    )
    service.method.add(
        name="UploadWidgets",
        input_type=".acme.widget.Widget",
        output_type=".acme.widget.Widget",
        client_streaming=True,
    )
    service.method.add(
        name="ChatWidgets",
        input_type=".acme.widget.Widget",
        output_type=".acme.widget.Widget",
        client_streaming=True,
        server_streaming=True,
    )
    response = generate(request)
    assert not response.error
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)
    usage = tmp_path / "typing_usage.py"
    usage.write_text("""\
from collections.abc import MutableMapping, MutableSequence

from nebius.aio.request import Request
from nebius.aio.stream import StreamRequest
from nebius.base.protos.extensions import Extension
from typed.acme.common import Shared, State
from typed.acme.extension import Host, Mode, mode, tag
from typed.acme.widget import (
    EXTENSIONS,
    EXTENSION_HANDLES,
    REGISTRY,
    Widget,
    WidgetServiceClient,
)


def check(widget: Widget, client: WidgetServiceClient) -> None:
    identifier: int = widget.id
    shared: Shared = widget.shared
    labels: MutableMapping[str, int] = widget.labels
    states: MutableSequence[State] = widget.states
    request: Request[Widget, Widget] = client.get_widget(widget)
    watch: StreamRequest[Widget, Widget] = client.watch_widgets(
        widget, wait_for_ready=True
    )
    upload: StreamRequest[Widget, Widget] = client.upload_widgets()
    chat: StreamRequest[Widget, Widget] = client.chat_widgets()
    constructed = Widget(
        id=identifier,
        shared=shared,
        labels=labels,
        states=states,
        kind=Widget.Kind.KIND_SPECIAL,
    )
    selected = constructed.choice
    if selected is not None:
        field: str = selected.field
    extension: Extension[str] = tag
    extension_value: str = Host().get_extension(extension)
    enum_extension: Extension[Mode] = mode
    enum_value: Mode = Host().get_extension(enum_extension)
""")
    environment = os.environ.copy()
    environment["MYPYPATH"] = os.pathsep.join(
        (str(tmp_path), str(Path(__file__).parents[2] / "src"))
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-incremental",
            str(usage),
        ],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    invalid_usage = tmp_path / "invalid_streaming_kwargs.py"
    invalid_usage.write_text("""\
from typed.acme.widget import Widget, WidgetServiceClient


def check(widget: Widget, client: WidgetServiceClient) -> None:
    client.watch_widgets(widget, retries=2)
""")
    invalid_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--no-incremental",
            str(invalid_usage),
        ],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid_result.returncode != 0
    assert 'Unexpected keyword argument "retries"' in invalid_result.stdout


def test_constructor_local_names_do_not_collide_with_fields(tmp_path: Path) -> None:
    request = _request("locals")
    message = request.proto_file[0].message_type.add(name="LocalNames")
    for number, name in enumerate(
        ("self", "initial_message", "values", "property", "after_property"), start=1
    ):
        _field(message, name, number, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    response = generate(request)
    assert not response.error
    source = _implementation_source(response, "locals/acme/common")
    compile(source, "generated", "exec")
    assert "\n    @property\n" not in source
    assert "@_NebiusProperty" in source


def test_runtime_typing_aliases_do_not_reserve_public_proto_names() -> None:
    request = _request("aliases")
    request.proto_file[0].message_type.add(name="Request")
    response = generate(request)
    assert not response.error
    source = _implementation_source(response, "aliases/acme/common")
    assert "class Request(Message):" in source


@pytest.mark.parametrize("field_kind", ("message", "enum", "renamed_message"))
def test_standard_type_symbols_alias_runtime_field_and_enum_imports(
    field_kind: str, tmp_path: Path
) -> None:
    standard = descriptor_pb2.FileDescriptorProto(
        name="google/protobuf/type_fixture.proto",
        package="google.protobuf",
        syntax="proto3",
    )
    field_message = standard.message_type.add(name="Field")
    if field_kind == "enum":
        field_message.name = "Holder"
    elif field_kind == "renamed_message":
        field_message.name = "Other"
        field_message.options.MergeFromString(_name_option(1195, 1, "Field"))
    _field(
        field_message,
        "name",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    if field_kind == "enum":
        field_enum = standard.enum_type.add(name="Field")
        field_enum.value.add(name="FIELD_UNSPECIFIED", number=0)
    standard.message_type.add(name="Enum")
    request = plugin_pb2.CodeGeneratorRequest(
        file_to_generate=[standard.name],
        proto_file=[standard],
        parameter=f"package_prefix=standard_{field_kind}",
    )

    response = generate(request)

    assert not response.error
    source = _implementation_source(response, f"standard_{field_kind}/google/protobuf")
    assert "Field as _NebiusField" in source
    assert "Enum as _NebiusEnum" in source
    expected_base = "_NebiusEnum" if field_kind == "enum" else "Message"
    assert f"class Field({expected_base}):" in source
    assert "class Enum(Message):" in source
    assert " = _NebiusField('name', 'name', 1, STRING" in source
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)
    namespace = f"standard_{field_kind}"
    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module(f"{namespace}.google.protobuf")
        message_type = module.Holder if field_kind == "enum" else module.Field
        assert message_type(name="value").name == "value"
        if field_kind == "enum":
            assert module.Field.FIELD_UNSPECIFIED == 0
    finally:
        sys.path.remove(str(tmp_path))
        for name in tuple(sys.modules):
            if name == namespace or name.startswith(namespace + "."):
                sys.modules.pop(name)


def test_collisions_fail_in_band() -> None:
    edition = _request("invalid")
    edition.proto_file[0].edition = descriptor_pb2.EDITION_2023
    assert "protobuf editions are not supported" in generate(edition).error

    cross_kind = _request("invalid")
    cross_kind.proto_file[0].message_type.add(name="State")
    assert "duplicate protobuf symbol 'acme.common.State'" in generate(cross_kind).error

    flattened = _request("invalid")
    flattened.proto_file[1].message_type.add(name="Widget__Extra")
    flattened.proto_file[1].message_type[0].nested_type.add(name="Extra")
    assert "Python symbol collision 'Widget__Extra'" in generate(flattened).error

    reserved = _request("invalid")
    reserved.proto_file[0].message_type.add(name="Message")
    assert "shadows generated import Message" in generate(reserved).error

    nested_runtime = _request("invalid")
    nested_runtime.proto_file[1].message_type[0].nested_type.add(
        name="SerializeToString"
    )
    assert "Python member collision" in generate(nested_runtime).error

    private_state = _request("invalid")
    private_state.proto_file[0].message_type[0].field.add(
        name="_values", number=2, label=1, type=9
    )
    assert (
        "Python field collision acme.common.Shared._values"
        in generate(private_state).error
    )

    for field_name in (
        "is_default",
        "check_presence",
        "which_field_in_oneof",
        "__PY_TO_PB2__",
        "_repr_field",
        "_oneof_python_name",
        "_NebiusProperty",
    ):
        helper_collision = _request("invalid")
        helper_collision.proto_file[0].message_type[0].field.add(
            name=field_name, number=2, label=1, type=9
        )
        assert "Python field collision" in generate(helper_collision).error

    enum_runtime = _request("invalid")
    enum_runtime.proto_file[0].enum_type[0].value.add(name="get_descriptor", number=2)
    assert "Python enum value collision" in generate(enum_runtime).error

    enum_normalized = _request("invalid")
    enum_normalized.proto_file[0].enum_type[0].value.add(name="class", number=2)
    enum_normalized.proto_file[0].enum_type[0].value.add(name="class_", number=3)
    assert "Python enum value collision" in generate(enum_normalized).error

    scoped_runtime = _request("invalid")
    scoped_runtime.proto_file[2].message_type[0].extension[0].name = "SerializeToString"
    assert "Python member collision" in generate(scoped_runtime).error

    for field_name in (
        "__str__",
        "__annotations__",
        "__module__",
        "__weakref__",
        "_format_map_key",
        "__x",
    ):
        field_dunder = _request("invalid")
        field_dunder.proto_file[0].message_type[0].field.add(
            name=field_name, number=2, label=1, type=9
        )
        assert "Python field collision" in generate(field_dunder).error

    nested_dunder = _request("invalid")
    nested_dunder.proto_file[0].message_type[0].nested_type.add(name="__repr__")
    assert "Python member collision" in generate(nested_dunder).error

    helper_collision = _request("invalid")
    helper_message = helper_collision.proto_file[0].message_type.add(
        name="OneofHelpers"
    )
    helper_message.oneof_decl.add(name="a")
    helper_message.oneof_decl.add(name="a_b")
    _field(
        helper_message,
        "b",
        1,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        oneof_index=0,
    )
    assert "Python oneof helper collision" in generate(helper_collision).error

    renamed_oneof_collision = _request("invalid")
    renamed_message = renamed_oneof_collision.proto_file[0].message_type.add(
        name="RenamedOneofs"
    )
    first = renamed_message.oneof_decl.add(name="foo")
    first.options.MergeFromString(_name_option(1192, 1, "bar"))
    second = renamed_message.oneof_decl.add(name="bar")
    second.options.MergeFromString(_name_option(1192, 1, "baz"))
    assert "Python oneof collision" in generate(renamed_oneof_collision).error

    for enum_name in (
        "__str__",
        "__annotations__",
        "__weakref__",
        "_ignore_",
        "_custom_",
        "__custom__",
        "__x",
    ):
        enum_special = _request("invalid")
        enum_special.proto_file[0].enum_type[0].value.add(name=enum_name, number=2)
        assert "Python enum value collision" in generate(enum_special).error

    for module_name in (
        "__all__",
        "__annotations__",
        "__class__",
        "__dict__",
        "__weakref__",
    ):
        module_special = _request("invalid")
        module_special.proto_file[0].message_type.add(name=module_name)
        assert "shadows generated import" in generate(module_special).error

    registry_package = _request("invalid")
    registry_package.proto_file[0].package = "_registry"
    assert "conflicts with generated registry" in generate(registry_package).error

    output_alias = _request("invalid")
    output_alias.proto_file.extend(
        [
            descriptor_pb2.FileDescriptorProto(name="empty.proto"),
            descriptor_pb2.FileDescriptorProto(
                name="unpackaged.proto", package="_unpackaged"
            ),
        ]
    )
    output_alias.file_to_generate.extend(("empty.proto", "unpackaged.proto"))
    output_alias.proto_file[-2].message_type.add(name="EmptyPackageMessage")
    output_alias.proto_file[-1].message_type.add(name="NamedPackageMessage")
    assert "share output" in generate(output_alias).error


def test_generated_wire_matches_reference_provider(tmp_path: Path) -> None:
    request = _request("reference_namespace")
    _materialize(tmp_path, "reference_namespace")
    pool = descriptor_pool.DescriptorPool()
    for proto in request.proto_file:
        pool.AddSerializedFile(proto.SerializeToString())
    reference = message_factory.GetMessageClass(
        pool.FindMessageTypeByName("acme.widget.Widget")
    )
    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("reference_namespace.acme.widget")
        direct = module.Widget(id=17, count=4, labels={"a": 1, "b": 2})
        provider = reference.FromString(direct.SerializeToString(deterministic=True))
        assert provider.id == 17
        assert provider.count == 4
        assert dict(provider.labels) == {"a": 1, "b": 2}
        assert (
            module.Widget.FromString(
                provider.SerializeToString(deterministic=True)
            ).count
            == 4
        )
    finally:
        sys.path.remove(str(tmp_path))


def test_unknown_nebius_annotations_drive_generated_api(tmp_path: Path) -> None:
    request = _request("annotated")
    common, widget_file, _ = request.proto_file
    state = common.enum_type[0]
    state.options.MergeFromString(_name_option(1191, 1, "Lifecycle"))
    state.value[1].options.MergeFromString(_name_option(1195, 1, "AVAILABLE"))

    widget = widget_file.message_type[0]
    widget.options.MergeFromString(_name_option(1195, 1, "Resource"))
    widget.oneof_decl[0].options.MergeFromString(_name_option(1192, 1, "selection"))
    widget.field[0].options.MergeFromString(
        _name_option(1195, 1, "identifier")
        + _option_field(1192, 0, 1)
        + _option_field(1193, 0, 1)
    )

    service = widget_file.service[0]
    service.options.MergeFromString(
        _option_field(1191, 2, b"widget-api") + _name_option(1195, 3, "Resources")
    )
    service.method[0].options.MergeFromString(
        _name_option(1195, 3, "fetch") + _option_field(1197, 0, 2)
    )

    response = generate(request)
    assert not response.error
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)

    sys.path.insert(0, str(tmp_path))
    try:
        common_module = importlib.import_module("annotated.acme.common")
        widget_module = importlib.import_module("annotated.acme.widget")
        resource = widget_module.Resource(
            identifier=17,
            state=common_module.Lifecycle.AVAILABLE,
            name="chosen",
        )
        assert resource.identifier == 17
        assert resource.WhichOneof("selection") == "name"
        assert resource.WhichOneof("choice") == "name"
        assert resource.selection is not None
        assert resource.selection.field == "name"
        assert resource.selection.value == "chosen"
        assert widget_module.Resource.is_sensitive("identifier")
        assert widget_module.Resource.is_credentials("identifier")
        assert widget_module.Resource.__PB2_DESCRIPTOR__ is resource.get_descriptor()
        assert widget_module.Resource.__PY_TO_PB2__["identifier"] == "id"
        assert common_module.Lifecycle.__PB2_DESCRIPTOR__ is not None
        assert widget_module.ResourcesClient.__PB2_DESCRIPTOR__ is not None
        assert "17" not in repr(resource)
        assert "**HIDDEN**" in repr(resource)
        assert widget_module.ResourcesClient.__api_service_name__ == "widget-api"

        routed: list[object] = []

        class Transport:
            def unary_unary(self, path, serializer, deserializer):
                assert path == "/acme.widget.WidgetService/GetWidget"

                def call(request, **kwargs):
                    assert serializer(request) == resource.SerializeToString()
                    return object()

                return call

        class Address:
            channel = Transport()

        class Channel:
            def parent_id(self):
                return None

            def get_channel_by_route(self, route):
                routed.append(route)
                return Address()

        pending = widget_module.ResourcesClient(Channel()).fetch(resource)
        assert pending.input_metadata()["X-ResetMask"]
        pending._send(None)
        assert routed[0].api_service_name == "widget-api"
        assert routed[0].registry is widget_module.REGISTRY
    finally:
        sys.path.remove(str(tmp_path))


def test_annotation_policy_follows_current_public_descriptor_schema() -> None:
    request = _request("renumbered")
    annotations = descriptor_pb2.FileDescriptorProto(
        name="nebius/annotations.proto",
        package="nebius",
        syntax="proto3",
    )
    _add_public_annotation_schema(annotations)
    extensions = {extension.name: extension for extension in annotations.extension}
    for number, extension in enumerate(extensions.values(), start=21001):
        extension.number = number
    messages = {message.name: message for message in annotations.message_type}
    for message in messages.values():
        for number, field in enumerate(message.field, start=11):
            field.number = number
    behavior = next(
        enum for enum in annotations.enum_type if enum.name == "MethodBehavior"
    )
    behavior_values = {
        "METHOD_BEHAVIOR_UNSPECIFIED": 0,
        "METHOD_UPDATER": -1,
        "METHOD_PAGINATED": 43,
        "METHOD_WITHOUT_GET": 44,
    }
    for value in behavior.value:
        value.number = behavior_values[value.name]
    behavior.options.allow_alias = True
    behavior.value.add(name="METHOD_MUTATING_ALIAS", number=-1)

    widget_file = request.proto_file[1]
    widget = widget_file.message_type[0]
    message_name_field = messages["MessagePySDKSettings"].field[0].number
    widget.options.MergeFromString(
        _name_option(
            extensions["message_py_sdk"].number,
            message_name_field,
            "CurrentResource",
        )
    )
    widget.options.deprecated = True
    details = messages["DeprecationDetails"]
    detail_fields = {field.name: field.number for field in details.field}
    widget.options.MergeFromString(
        _option_field(
            extensions["message_deprecation_details"].number,
            2,
            _option_field(detail_fields["effective_at"], 2, b"2029-03-04")
            + _option_field(detail_fields["description"], 2, b"use the successor"),
        )
    )
    field = widget.field[0]
    field.options.MergeFromString(
        _option_field(extensions["sensitive"].number, 0, 1)
        + _option_field(extensions["credentials"].number, 0, 1)
    )
    service = widget_file.service[0]
    service.options.MergeFromString(
        _option_field(extensions["api_service_name"].number, 2, b"current-widget-api")
    )
    service.method[0].options.MergeFromString(
        _option_field(
            extensions["method_behavior"].number,
            0,
            (1 << 64) - 1,
        )
    )
    request.proto_file.append(annotations)

    response = generate(request)

    assert not response.error
    source = _implementation_source(response, "renumbered/acme/widget")
    assert "class CurrentResource(Message):" in source
    assert "sensitive=True" in source
    assert "credentials=True" in source
    assert "Supported until 03/04/29. Use the successor." in source
    assert "__api_service_name__ = 'current-widget-api'" in source
    assert "ensure_reset_mask_in_metadata" in source


def test_invalid_annotated_names_fail_in_band() -> None:
    request = _request("invalid")
    request.proto_file[1].message_type[0].options.MergeFromString(
        _name_option(1195, 1, "not_a_class")
    )

    assert "invalid annotated Python class name" in generate(request).error

    ambiguous_oneof = _request("invalid")
    widget = ambiguous_oneof.proto_file[1].message_type[0]
    widget.field[0].options.MergeFromString(_name_option(1195, 1, "identifier"))
    widget.oneof_decl[0].options.MergeFromString(_name_option(1192, 1, "id"))

    assert (
        "Python oneof collision acme.widget.Widget.id"
        in generate(ambiguous_oneof).error
    )

    duplicate_extensions = _request("invalid")
    host = duplicate_extensions.proto_file[2].message_type[0]
    second = host.extension.add(
        name="tag2",
        number=102,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        extendee=".acme.extension.Host",
    )
    host.extension[0].options.MergeFromString(_name_option(1195, 1, "same"))
    second.options.MergeFromString(_name_option(1195, 1, "same"))

    assert "Python scoped extension collision" in generate(duplicate_extensions).error


def test_user_client_symbol_does_not_collide_with_private_runtime_import() -> None:
    request = _request("client_symbol")
    request.proto_file[1].message_type.add(name="Client")

    response = generate(request)

    assert not response.error
    package = _implementation_source(response, "client_symbol/acme/widget")
    assert "class Client(Message):" in package
    assert "Client as _NebiusClient" in package

    for reserved_name in (
        "_NebiusClient",
        "_NebiusClientWithOperations",
        "_NebiusOperation",
        "_NebiusRequestStatus",
        "_nebius_request_status_to_status",
        "_nebius_status_to_request_status",
    ):
        reserved = _request("client_symbol")
        reserved.proto_file[1].message_type.add(name=reserved_name)

        assert f"shadows generated import {reserved_name}" in generate(reserved).error


def test_source_docs_and_deprecation_are_emitted_in_every_partition(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def request(partition: str) -> plugin_pb2.CodeGeneratorRequest:
        file = descriptor_pb2.FileDescriptorProto(
            name="acme/documented.proto",
            package="acme.documented",
            syntax="proto3",
        )
        message = file.message_type.add(name="Documented")
        field = message.field.add(name="value", number=1, label=1, type=9)
        enum = file.enum_type.add(name="State")
        enum.value.add(name="STATE_UNSPECIFIED", number=0)
        ready = enum.value.add(name="STATE_READY", number=1)
        ready.options.deprecated = True
        _field(
            message,
            "state",
            2,
            descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
            type_name=".acme.documented.State",
        )
        service = file.service.add(name="DocumentedService")
        method = service.method.add(
            name="Get",
            input_type=".acme.documented.Documented",
            output_type=".acme.documented.Documented",
        )

        details = _option_field(1, 2, b"2027-01-02") + _option_field(
            2, 2, b"use the replacement"
        )
        for options in (
            message.options,
            field.options,
            service.options,
            method.options,
        ):
            options.deprecated = True
            options.MergeFromString(_option_field(1194, 2, details))

        locations = (
            ((4, 0), "Message leading.", "Message trailing.", ("Message detached.",)),
            ((4, 0, 2, 0), "Field leading.", "Field trailing.", ()),
            ((5, 0), "Enum leading.", "", ("Enum detached.",)),
            ((5, 0, 2, 1), "Ready value leading.", "", ()),
            ((6, 0), "Service leading.", "", ()),
            ((6, 0, 2, 0), "Method leading.", "Method trailing.", ()),
        )
        for path, leading, trailing, detached in locations:
            location = file.source_code_info.location.add(path=path)
            location.leading_comments = f" {leading}" if leading else ""
            location.trailing_comments = f" {trailing}" if trailing else ""
            location.leading_detached_comments.extend(
                f" {comment}" for comment in detached
            )
        return plugin_pb2.CodeGeneratorRequest(
            proto_file=[file],
            file_to_generate=[file.name],
            parameter=(
                f"package_prefix=documented_{partition},"
                f"partition={partition},jobs=2"
            ),
        )

    generated: dict[str, str] = {}
    for partition in ("all", "package", "directory"):
        response = generate(request(partition))
        assert not response.error
        package = _implementation_source(
            response, f"documented_{partition}/acme/documented"
        )
        generated[partition] = package.replace(f"documented_{partition}", "documented")
        for output in response.file:
            path = tmp_path / output.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(output.content)

    assert generated["all"] == generated["package"] == generated["directory"]
    assert "Ready value leading." in generated["all"]

    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("documented_all.acme.documented")
        assert "Message detached." in module.Documented.__doc__
        assert "Message leading." in module.Documented.__doc__
        assert "Message trailing." in module.Documented.__doc__
        assert "Supported until 01/02/27." in module.Documented.__doc__
        assert "Field leading." in module.Documented.value.fget.__doc__
        assert "Field trailing." in module.Documented.value.fget.__doc__
        assert "Enum detached." in module.State.__doc__
        assert "Service leading." in module.DocumentedServiceClient.__doc__
        assert "Method leading." in module.DocumentedServiceClient.get.__doc__
        assert "Method trailing." in module.DocumentedServiceClient.get.__doc__

        class Channel:
            pass

        with caplog.at_level("WARNING", logger="deprecation"):
            value = module.Documented(value="before", state=module.State.STATE_READY)
            assert value.value == "before"
            value.value = "after"
            module.DocumentedServiceClient(Channel()).get(value)
        messages = [record.getMessage() for record in caplog.records]
        expected = (
            "Message acme.documented.Documented is deprecated",
            "Field acme.documented.Documented.value is deprecated",
            "Setting deprecated enum value acme.documented.State.STATE_READY",
            "Service acme.documented.DocumentedService is deprecated",
            "Method acme.documented.DocumentedService.Get is deprecated",
        )
        assert all(
            any(needle in message for message in messages) for needle in expected
        )
    finally:
        sys.path.remove(str(tmp_path))


def test_parent_package_and_service_namespaces_are_protected() -> None:
    def package_request(parent_name: str, child_component: str):
        parent = descriptor_pb2.FileDescriptorProto(
            name="parent.proto", package="p", syntax="proto3"
        )
        message = parent.message_type.add(name=parent_name)
        if parent_name == "Host":
            message.field.add(name="id", number=1, label=1, type=9)
        child = descriptor_pb2.FileDescriptorProto(
            name="child.proto", package=f"p.{child_component}", syntax="proto3"
        )
        child.message_type.add(name="Child")
        return plugin_pb2.CodeGeneratorRequest(
            proto_file=[parent, child],
            file_to_generate=[parent.name, child.name],
            parameter="package_prefix=invalid",
        )

    for parent_name, child_component in (
        ("child", "child"),
        ("Host", "REGISTRY"),
        ("Host", "Message"),
        ("Host", "_P_HOST_ID"),
    ):
        assert (
            "Python symbol"
            in generate(package_request(parent_name, child_component)).error
        )

    for method_name in (
        "__init__",
        "__service_name__",
        "_channel",
        "request",
        "__str__",
        "__annotations__",
        "__dict__",
        "__module__",
        "__weakref__",
        "__x",
    ):
        request = _request("invalid")
        request.proto_file[1].service[0].method[0].name = method_name
        assert "Python method collision" in generate(request).error


@pytest.mark.parametrize("package", ("_registry", "_registry_fragment"))
def test_root_registry_module_names_are_reserved(package: str) -> None:
    file = descriptor_pb2.FileDescriptorProto(
        name=f"{package}.proto", package=package, syntax="proto3"
    )
    file.message_type.add(name="Collision")
    request = plugin_pb2.CodeGeneratorRequest(
        proto_file=[file],
        file_to_generate=[file.name],
        parameter="package_prefix=invalid",
    )

    assert "conflicts with generated registry" in generate(request).error
