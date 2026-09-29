"""Deprecation diagnostics distinguish user actions from SDK and server work."""

import asyncio
import logging
import sys
from types import SimpleNamespace

import pytest
from nebius.aio.client import Client
from nebius.aio.operation import Operation
from nebius.api.nebius.common.v1alpha1 import GetOperationRequest, OperationServiceClient
from nebius.api.nebius.common.v1alpha1 import Operation as OperationMessage
from nebius.api.nebius.compute.v1 import PlatformSpec
from nebius.base.protos import direct
from nebius.base.protos.codec import STRING
from nebius.base.protos.direct import Field, Message, message_codec


@pytest.fixture(autouse=True)
def isolated_warnings(monkeypatch, caplog):
    monkeypatch.setattr(direct, "_DEPRECATION_SEEN", set())
    caplog.set_level(logging.WARNING, logger="deprecation")


def test_repeated_user_construction_warns_once_without_stack(caplog):
    for _ in range(100):
        expected_line = sys._getframe().f_lineno + 1
        GetOperationRequest(id="test-operation")

    assert len(caplog.records) == 1
    assert "GetOperationRequest" in caplog.records[0].message
    assert caplog.records[0].stack_info is None
    assert caplog.records[0].pathname == __file__
    assert caplog.records[0].lineno == expected_line


def test_explicit_service_construction_warns_once(monkeypatch, caplog):
    monkeypatch.setattr(Client, "request", lambda *args, **kwargs: None)
    for _ in range(3):
        expected_line = sys._getframe().f_lineno + 1
        OperationServiceClient(object()).get(GetOperationRequest(id="test"))

    messages = [record.message for record in caplog.records]
    assert len(messages) == 2
    assert sum(message.startswith("Service ") for message in messages) == 1
    assert all(record.stack_info is None for record in caplog.records)
    assert all(record.pathname == __file__ and record.lineno == expected_line for record in caplog.records)


@pytest.mark.parametrize("parse", ["FromString", "ParseFromString", "MergeFromString"])
def test_nested_server_messages_and_field_reads_are_silent(caplog, parse):
    field = Field("legacy", "legacy", 1, STRING, deprecation_details="Use the new field.")

    class Child(Message):
        __PROTO_FULL_NAME__ = "test.DeprecatedChild"
        __DEPRECATION_DETAILS__ = "Use the new message."
        __FIELDS__ = (field,)

    child_field = Field("child", "child", 1, message_codec(lambda: Child))

    class Parent(Message):
        __FIELDS__ = (child_field,)

    payload = b"\x0a\x05\x0a\x03old"
    if parse == "FromString":
        message = Parent.FromString(payload)
    else:
        message = Parent()
        getattr(message, parse)(payload)
    copied = Parent(message)
    merged = Parent()
    merged.MergeFrom(message)
    replaced = Parent()
    replaced.CopyFrom(message)
    for received in (message, copied, merged, replaced):
        assert received._get_field(child_field)._get_field(field) == "old"
    child = message._get_field(child_field)
    assert Parent.FromString(b"")._get_field(child_field)._get_field(field) == ""
    assert caplog.records == []

    expected_line = sys._getframe().f_lineno + 1
    child._set_field(field, "new")
    assert len(caplog.records) == 1
    assert caplog.records[0].pathname == __file__
    assert caplog.records[0].lineno == expected_line
    assert "Field test.DeprecatedChild.legacy" in caplog.records[0].message
    Child()
    assert len(caplog.records) == 2
    assert "Message test.DeprecatedChild" in caplog.records[1].message


def test_internal_polling_is_silent_without_consuming_user_warning(monkeypatch, caplog):
    message = OperationMessage.FromString(b"\x0a\x04test")
    operation = Operation("example.Service.Create", SimpleNamespace(parent_id=lambda: ""), message)
    calls = []

    async def response():
        return SimpleNamespace(_operation=message)

    def request(self, method, request, *args, **kwargs):
        calls.append(request.id)
        return response()

    monkeypatch.setattr(Client, "request", request)

    async def poll():
        for _ in range(3):
            await operation.update()

    asyncio.run(poll())
    assert calls == ["test"] * 3
    assert caplog.records == []

    GetOperationRequest(id="user-operation")
    assert len(caplog.records) == 1


def test_suppression_is_task_local_and_resets_after_exception(caplog):
    async def suppressed():
        with pytest.raises(RuntimeError), direct.suppress_deprecation_warnings():
            await asyncio.sleep(0)
            direct.deprecation_warning("test", "suppressed")
            raise RuntimeError
        direct.deprecation_warning("test", "after")

    async def user():
        direct.deprecation_warning("test", "user")

    async def run():
        await asyncio.gather(suppressed(), user())

    asyncio.run(run())
    assert [record.message for record in caplog.records] == [
        "user is deprecated. test",
        "after is deprecated. test",
    ]


@pytest.mark.parametrize(
    "container,mutation",
    [
        ("map", "set"),
        ("map", "update"),
        ("repeated", "append"),
        ("repeated", "extend"),
        ("message", "set"),
    ],
)
def test_deprecated_field_mutations_warn_but_reads_and_decoding_do_not(container, mutation, caplog):
    child_field = Field("value", "value", 1, STRING)

    class Child(Message):
        __FIELDS__ = (child_field,)

    field = Field(
        "legacy",
        "legacy",
        1,
        message_codec(lambda: Child) if container == "message" else STRING,
        map_key_codec=STRING if container == "map" else None,
        repeated=container == "repeated",
        deprecation_details="Use the new field.",
    )

    class Parent(Message):
        __PROTO_FULL_NAME__ = "test.DeprecatedContainer"
        __FIELDS__ = (field,)

    payload = {
        "map": b"\x0a\x08\x0a\x01k\x12\x03old",
        "repeated": b"\x0a\x03old",
        "message": b"\x0a\x05\x0a\x03old",
    }[container]
    message = Parent.FromString(payload)
    value = message._get_field(field)
    if container == "message":
        value.ParseFromString(b"\x0a\x03old")
    assert caplog.records == []
    for _ in range(2):
        if container == "map":
            assert value["k"]
            if mutation == "update":
                expected_line = sys._getframe().f_lineno + 1
                value.update(k="new")
            else:
                expected_line = sys._getframe().f_lineno + 1
                value["k"] = "new"
        elif container == "repeated":
            assert value[0]
            if mutation == "extend":
                expected_line = sys._getframe().f_lineno + 1
                value.extend(["new"])
            else:
                expected_line = sys._getframe().f_lineno + 1
                value.append("new")
        else:
            assert value._get_field(child_field)
            expected_line = sys._getframe().f_lineno + 1
            value._set_field(child_field, "new")
    assert len(caplog.records) == 1
    assert "Field test.DeprecatedContainer.legacy" in caplog.records[0].message
    assert caplog.records[0].pathname == __file__
    assert caplog.records[0].lineno == expected_line


def test_suppressed_and_duplicate_warnings_do_not_inspect_frames(monkeypatch, caplog):
    direct.deprecation_warning("details", "seen")

    def unexpected_frame_walk():
        raise AssertionError("suppressed or duplicate warning inspected frames")

    monkeypatch.setattr(direct, "currentframe", unexpected_frame_walk)
    direct.deprecation_warning("details", "seen")
    with direct.suppress_deprecation_warnings():
        direct.deprecation_warning("details", "suppressed")
    assert len(caplog.records) == 1


def test_generated_field_assignment_identifies_the_caller(caplog):
    message = PlatformSpec()
    expected_line = sys._getframe().f_lineno + 1
    message.gpu_memory_gibibytes = 1

    assert len(caplog.records) == 1
    assert caplog.records[0].pathname == __file__
    assert caplog.records[0].lineno == expected_line


def test_explicit_stacklevel_override_is_preserved(caplog):
    expected_line = sys._getframe().f_lineno + 1
    direct.deprecation_warning("details", "explicit", stacklevel=2)

    assert caplog.records[0].pathname == __file__
    assert caplog.records[0].lineno == expected_line
