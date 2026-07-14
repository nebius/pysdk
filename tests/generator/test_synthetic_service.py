"""End-to-end test for the generated all-types synthetic service."""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import grpc
import grpc.aio
import pytest
from google.protobuf import descriptor_pool, json_format, message_factory
from google.rpc import code_pb2

from nebius.aio.channel import Channel, NoCredentials
from nebius.base.fieldmask import Mask
from nebius.base.options import INSECURE
from nebius.base.resolver import Constant
from nebius_generator.main import generate
from tests.generator.synthetic_service import (
    MAP_KEY_TYPES,
    SCALARS,
    WELL_KNOWN_TYPES,
    synthetic_request,
)
from tests.grpc_service import add_service


def _materialize(tmp_path: Path, namespace: str) -> None:
    response = generate(synthetic_request(namespace))
    assert not response.error
    for output in response.file:
        path = tmp_path / output.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output.content)


def _mask_paths(mask: Mask) -> set[str]:
    paths: set[str] = set()
    pending: list[tuple[tuple[str, ...], Mask]] = [((), mask)]
    while pending:
        prefix, current = pending.pop()
        children = [("*", current.any)] if current.any is not None else []
        children.extend(
            (key.marshal(), child) for key, child in current.field_parts.items()
        )
        for name, child in children:
            path = (*prefix, name)
            if child.is_empty():
                paths.add(".".join(path))
            else:
                pending.append((path, child))
    return paths


def _reference_type(request: Any) -> tuple[type[Any], descriptor_pool.DescriptorPool]:
    pool = descriptor_pool.DescriptorPool()
    pending = list(request.proto_file)
    while pending:
        remaining = []
        progressed = False
        for proto in pending:
            try:
                pool.AddSerializedFile(proto.SerializeToString(deterministic=True))
            except TypeError:
                remaining.append(proto)
            else:
                progressed = True
        if not progressed:
            raise AssertionError(
                f"could not link synthetic descriptors: {[p.name for p in remaining]}"
            )
        pending = remaining
    descriptor = pool.FindMessageTypeByName("synthetic.everything.v1.AllTypes")
    return message_factory.GetMessageClass(descriptor), pool


def _map_key(type_: int, index: int) -> object:
    from google.protobuf.descriptor_pb2 import FieldDescriptorProto as F

    if type_ == F.TYPE_STRING:
        return f"key-{index}"
    if type_ == F.TYPE_BOOL:
        return True
    return index + 1


def _populated_reference(reference_type: type[Any]) -> Any:
    message = reference_type()
    for name, _, value in SCALARS:
        setattr(message, name, value)
        getattr(message, f"repeated_{name}").extend([value, value])
    message.state = 1
    message.child.text = "child"
    message.child.count = 7
    message.recursive.value = "root"
    message.recursive.next.value = "leaf"
    message.display_label = "custom-json-name"
    message.repeated_state.extend([0, 1, -1])
    repeated_child = message.repeated_child.add()
    repeated_child.text = "repeated"
    message.repeated_timestamp.add(seconds=1, nanos=2)

    descriptor = message.DESCRIPTOR
    for index, (name, _, value) in enumerate(SCALARS):
        field = descriptor.fields_by_name[f"map_{name}"]
        key = _map_key(field.message_type.fields_by_name["key"].type, index)
        getattr(message, f"map_{name}")[key] = value
    message.map_state["ready"] = 1
    message.map_child["child"].text = "mapped"
    message.map_timestamp["created"].seconds = 3
    message.map_timestamp["created"].nanos = 4

    message.any_value.type_url = "type.googleapis.com/synthetic.everything.v1.Child"
    message.any_value.value = message.child.SerializeToString(deterministic=True)
    message.duration_value.seconds = 5
    message.duration_value.nanos = 6
    message.empty_value.SetInParent()
    message.field_mask_value.paths.extend(["child.text", "state"])
    json_format.ParseDict(
        {"number": 1.5, "null": None, "items": [True, "x"]},
        message.struct_value,
    )
    message.empty_struct_value.SetInParent()
    json_format.ParseDict(None, message.value_value)
    json_format.ParseDict([None, False, {"nested": "value"}], message.list_value)
    message.empty_list_value.SetInParent()
    message.timestamp_value.seconds = 7
    message.timestamp_value.nanos = 8
    message.bool_wrapper.value = True
    message.bytes_wrapper.value = b"wrapped"
    message.double_wrapper.value = 9.25
    message.float_wrapper.value = -10.5
    message.int32_wrapper.value = -11
    message.int64_wrapper.value = -(2**43)
    message.string_wrapper.value = "wrapped"
    message.uint32_wrapper.value = 12
    message.uint64_wrapper.value = 2**43
    message.status_value.code = 3
    message.status_value.message = "synthetic status"
    message.rpc_code = code_pb2.PERMISSION_DENIED

    for name, _, _ in SCALARS:
        setattr(message, f"optional_{name}", getattr(reference_type(), name))
    message.optional_state = 0
    message.choice_child.text = "chosen"
    return message


@pytest.mark.asyncio
async def test_generated_all_types_service_end_to_end(tmp_path: Path) -> None:
    namespace = "synthetic_test_sdk"
    request = synthetic_request(namespace)
    _materialize(tmp_path, namespace)
    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module(f"{namespace}.synthetic.everything.v1")
        rpc_module = importlib.import_module(f"{namespace}.google.rpc")
        direct_type = module.AllTypes
        reference_type, reference_pool = _reference_type(request)
        reference = _populated_reference(reference_type)
        reference_wire = reference.SerializeToString(deterministic=True)
        declared_field_wrong_wire = b"\x98\x06\x07"
        unknown_field = b"\xc0\x0c\x07"
        unknown_suffix = declared_field_wrong_wire + unknown_field
        direct = direct_type.FromString(reference_wire + unknown_suffix)

        descriptor = direct_type.get_descriptor()
        assert {field.type for field in descriptor.fields[:15]} == set(range(1, 19)) - {
            10,
            11,
            14,
        }
        assert descriptor.fields_by_name["display_label"].json_name == (
            "displayLabelCustom"
        )
        map_fields = [
            field for field in descriptor.fields if field.name.startswith("map_")
        ]
        assert {
            field.message_type.fields_by_name["key"].type for field in map_fields
        } == set(MAP_KEY_TYPES)
        assert {
            descriptor.fields_by_name[name].message_type.full_name
            for name, _ in WELL_KNOWN_TYPES
        } == {type_name.lstrip(".") for _, type_name in WELL_KNOWN_TYPES}
        assert all(direct.check_presence(f"optional_{name}") for name, _, _ in SCALARS)
        assert direct.check_presence("optional_state")
        assert direct.WhichOneof("choice") == "choice_child"
        assert direct.rpc_code is rpc_module.Code.PERMISSION_DENIED
        assert direct.rpc_code.value == code_pb2.PERMISSION_DENIED
        assert direct.recursive.next.value == "leaf"
        assert json.loads(direct.struct_value.to_json()) == {
            "items": [True, "x"],
            "null": None,
            "number": 1.5,
        }
        assert json.loads(direct.empty_struct_value.to_json()) == {}
        assert json.loads(direct.value_value.to_json()) is None
        assert json.loads(direct.list_value.to_json()) == [
            None,
            False,
            {"nested": "value"},
        ]
        assert json.loads(direct.empty_list_value.to_json()) == []
        assert direct.check_presence("empty_struct_value")
        assert direct.check_presence("value_value")
        assert direct.check_presence("empty_list_value")
        absent = direct_type()
        assert not absent.check_presence("empty_struct_value")
        assert not absent.check_presence("value_value")
        assert not absent.check_presence("empty_list_value")

        direct_wire = direct.SerializeToString(deterministic=True)
        assert direct_wire == reference_wire + unknown_suffix
        provider_json = json.loads(
            json_format.MessageToJson(reference, descriptor_pool=reference_pool)
        )
        direct_json = json.loads(direct.to_json())
        assert direct_json == provider_json
        assert (
            direct_type.from_json(direct.to_json()).SerializeToString(
                deterministic=True
            )
            == reference_wire
        )

        views = direct_type.FromString(reference_wire)
        assert list(views.repeated_int32_value) == [-123, -123]
        views.repeated_int32_value.append(321)
        assert list(views.repeated_int32_value) == [-123, -123, 321]
        assert views.map_int32_value[3] == -123
        views.map_int32_value[-4] = 456
        assert views.map_int32_value[-4] == 456
        mutated = direct_type.FromString(views.SerializeToString(deterministic=True))
        assert list(mutated.repeated_int32_value) == [-123, -123, 321]
        assert mutated.map_int32_value[-4] == 456
        assert isinstance(views.timestamp_value, datetime)
        assert views.timestamp_value.timestamp() == 7
        assert views.duration_value == timedelta(seconds=5, microseconds=0)
        assert [value.timestamp() for value in views.repeated_timestamp] == [1]
        assert views.map_timestamp["created"].timestamp() == 3
        assert views.bool_wrapper.value is True
        assert views.bytes_wrapper.value == b"wrapped"
        assert views.uint64_wrapper.value == 2**43
        assert views.status_value.code is grpc.StatusCode.INVALID_ARGUMENT
        assert views.status_value.message == "synthetic status"
        assert views.status_value.registry is module.REGISTRY

        reset_paths = _mask_paths(direct.get_full_update_reset_mask())
        assert "proto_reset_name" in reset_paths
        assert "protoResetCustom" not in reset_paths
        assert "display_label" not in reset_paths
        assert "child" in reset_paths
        assert "recursive.next.next" in reset_paths
        assert "map_child.*.count" in reset_paths
        assert "map_timestamp.*" in reset_paths
        assert "optional_double_value" in reset_paths
        assert "optional_state" in reset_paths
        assert "choice_child.count" in reset_paths

        assert module.REGISTRY is direct_type.__REGISTRY__
        unpacked = module.REGISTRY.unpack_any(direct.any_value)
        assert type(unpacked) is module.Child
        assert unpacked.text == "child"
        assert (
            direct_type.__REGISTRY__.message_class("synthetic.everything.v1.AllTypes")
            is direct_type
        )

        service = module.AllTypesServiceClient.get_descriptor()
        assert {
            (method.client_streaming, method.server_streaming)
            for method in service.methods
        } == {(False, False), (False, True), (True, False), (True, True)}

        class Implementation:
            async def Echo(self, value: Any, context: Any) -> Any:  # noqa: N802
                return value

            async def Expand(  # noqa: N802
                self, value: Any, context: Any
            ) -> AsyncIterator[Any]:
                yield value
                expanded = direct_type(value)
                expanded.string_value = "expanded"
                yield expanded

            async def Collect(self, values: Any, context: Any) -> Any:  # noqa: N802
                result = direct_type()
                async for value in values:
                    result = value
                return result

            async def Chat(  # noqa: N802
                self, values: Any, context: Any
            ) -> AsyncIterator[Any]:
                async for value in values:
                    yield value

        server = grpc.aio.server()
        channel: Channel | None = None
        try:
            port = server.add_insecure_port("127.0.0.1:0")
            add_service(server, module.AllTypesServiceClient, Implementation())
            await server.start()
            channel = Channel(
                resolver=Constant(f"127.0.0.1:{port}"),
                options=[(INSECURE, True)],
                credentials=NoCredentials(),
            )
            client = module.AllTypesServiceClient(channel)
            first = direct_type.FromString(reference_wire)
            second = direct_type(string_value="second", child=module.Child(text="two"))
            echoed = await client.echo(first)
            assert echoed.SerializeToString(deterministic=True) == reference_wire

            expanded = [item async for item in client.expand(first)]
            assert [item.string_value for item in expanded] == [
                "synthetic",
                "expanded",
            ]
            assert expanded[0].recursive.next.value == "leaf"

            collect = client.collect()
            await collect.write(first)
            await collect.write(second)
            await collect.done_writing()
            collected = await collect
            assert collected.string_value == "second"
            assert collected.child.text == "two"

            chat = client.chat()
            await chat.write(first)
            await chat.write(second)
            await chat.done_writing()
            chatted = [item async for item in chat]
            assert [item.string_value for item in chatted] == ["synthetic", "second"]
            assert chatted[0].choice.value.text == "chosen"
            assert chatted[1].child.text == "two"
        finally:
            if channel is not None:
                await channel.close()
            await server.stop(0)
    finally:
        sys.path.remove(str(tmp_path))
        for name in tuple(sys.modules):
            if name == namespace or name.startswith(f"{namespace}."):
                del sys.modules[name]
