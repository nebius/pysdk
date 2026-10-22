"""Regression checks for the SDK audit findings."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from textwrap import dedent

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from nebius.aio.token.file_cache import async_renewable_bearer as cache_module
from nebius.aio.token.file_cache.async_renewable_bearer import AsynchronousRenewableFileCacheBearer
from nebius.aio.token.options import OPTION_RENEW_REQUIRED, OPTION_RENEW_SYNCHRONOUS, OPTION_REPORT_ERROR
from nebius.aio.token.static import Bearer
from nebius.aio.token.token import NamedBearer, Token
from nebius.base.metadata import Metadata
from nebius.base.protos.dynamic import enum_class, extension, message_class, register_file


@pytest.mark.asyncio()
@pytest.mark.parametrize("outcome", ["success", "failure", "cancel", "timeout"])
@pytest.mark.parametrize("wait_mode", [OPTION_REPORT_ERROR, OPTION_RENEW_SYNCHRONOUS])
@pytest.mark.parametrize("phase", ["starting", "running"])
async def test_file_cache_concurrent_waiters(tmp_path, monkeypatch, outcome, wait_mode, phase):
    started, release, second_ready = asyncio.Event(), asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(cache_module, "DEFAULT_CONFIG_DIR", tmp_path)
    bearer = AsynchronousRenewableFileCacheBearer(NamedBearer(Bearer("unused"), "concurrent"))
    reads = 0

    async def get():
        nonlocal reads
        reads += 1
        if reads == 2:
            second_ready.set()

    async def fetch(timeout=None, options=None):
        started.set()
        await release.wait()
        if outcome == "failure":
            raise RuntimeError("source failed")
        return Token("renewed")

    monkeypatch.setattr(bearer._file_cache, "get", get)
    monkeypatch.setattr(
        bearer._source.receiver().__class__, "_fetch", lambda self, *args, **kwargs: fetch(*args, **kwargs)
    )
    options = {wait_mode: "1"}
    first = asyncio.create_task(bearer.fetch(0.03 if outcome == "timeout" else 1, options))
    second = asyncio.create_task(bearer.fetch(1, options)) if phase == "starting" else None
    try:
        await asyncio.wait_for(started.wait(), 1)
        if second is None:
            second = asyncio.create_task(bearer.fetch(1, options))
        await asyncio.wait_for(second_ready.wait(), 1)
        if outcome == "cancel":
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
        elif outcome == "timeout":
            with pytest.raises(asyncio.TimeoutError):
                await first
        release.set()
        if outcome == "failure":
            results = await asyncio.gather(first, second, return_exceptions=True)
            assert all(isinstance(result, RuntimeError) and str(result) == "source failed" for result in results)
        else:
            if outcome == "success":
                assert (await first).token == "renewed"
            assert (await second).token == "renewed"
    finally:
        release.set()
        for task in (first, second):
            if task is not None:
                task.cancel()
        await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)
        await bearer.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize("exponent", [2, 1e200])
async def test_file_cache_backoff_increases_caps_and_resets(tmp_path, monkeypatch, exponent):
    monkeypatch.setattr(cache_module, "DEFAULT_CONFIG_DIR", tmp_path)
    bearer = AsynchronousRenewableFileCacheBearer(
        NamedBearer(Bearer("unused"), "backoff"),
        initial_retry_timeout=timedelta(seconds=1),
        retry_timeout_exponent=exponent,
        max_retry_timeout=timedelta(seconds=3),
    )
    delays, attempts = [], []
    outcomes = iter([False, False, False, True, False, True])

    async def sleep(delay):
        delays.append(delay)

    async def fetch(timeout=None, options=None):
        attempts.append(bearer._renewal_attempt)
        if not next(outcomes):
            raise RuntimeError("source failed")
        if len(attempts) == 6:
            bearer.stop()
        return Token("renewed")

    monkeypatch.setattr(cache_module, "sleep", sleep)
    monkeypatch.setattr(
        bearer._source.receiver().__class__, "_fetch", lambda self, *args, **kwargs: fetch(*args, **kwargs)
    )
    try:
        await asyncio.wait_for(bearer._run(), 2)
        assert delays[:4] == [0, 1, min(exponent, 3), 3]
        assert delays[5] == 1
        assert attempts == [1, 2, 3, 4, 1, 2]
        assert bearer._renewal_attempt == 0
    finally:
        await bearer.close()


@pytest.mark.parametrize(
    "index,replacement",
    [
        (slice(1, 1), [("NEW", "1")]),
        (slice(0, 1), [("A", "1"), ("B", "2")]),
        (slice(None), [("ONLY", "1")]),
        (slice(None), []),
        (slice(None, None, 2), [("A", "1"), ("B", "2")]),
        (slice(None, None, -1), [("A", "1"), ("B", "2"), ("C", "3")]),
    ],
)
def test_metadata_slice_matches_list(index, replacement):
    expected = [("x", "1"), ("y", "2"), ("z", "3")]
    metadata = Metadata(expected)
    expected[index] = [(key.lower(), value) for key, value in replacement]
    metadata[index] = iter(replacement)
    assert list(metadata) == expected


@pytest.mark.parametrize(
    "index,replacement,error",
    [
        (slice(None, None, 2), [("a", "1")], ValueError),
        (slice(None), [("a", "1"), ("b", 2)], TypeError),
        (0, ("a", 2), TypeError),
    ],
)
def test_metadata_invalid_assignment_is_atomic(index, replacement, error):
    original = [("x", "1"), ("y", "2"), ("z", "3")]
    metadata = Metadata(original)
    with pytest.raises(error):
        metadata[index] = replacement
    assert list(metadata) == original


def test_generated_scalar_and_extension_defaults_preserve_absence(monkeypatch):
    from nebius.base.protos import dynamic

    registry = dynamic.DynamicRegistry()
    registry._all_modules_loaded = True
    monkeypatch.setattr(dynamic, "REGISTRY", registry)
    for attribute in ("_MESSAGES", "_ENUMS", "_CLIENTS", "_INITIAL_PARAMETER_NAMES", "_ANNOTATION_DEPENDENTS"):
        monkeypatch.setattr(dynamic, attribute, {})
    for attribute in ("_EXPORTED_MESSAGES", "_EXPORTED_ENUMS", "_EXTENDEES"):
        monkeypatch.setattr(dynamic, attribute, set())
    extensions = type(dynamic.EXTENSIONS)()
    handles = type(dynamic.EXTENSION_HANDLES)()
    for attribute in ("_EXTENSIONS", "EXTENSIONS"):
        monkeypatch.setattr(dynamic, attribute, extensions)
    for attribute in ("_EXTENSION_HANDLES", "EXTENSION_HANDLES"):
        monkeypatch.setattr(dynamic, attribute, handles)

    proto = descriptor_pb2.FileDescriptorProto(name="audit/defaults.proto", package="audit.defaults", syntax="proto2")
    enum = proto.enum_type.add(name="State")
    enum.value.add(name="FIRST", number=5)
    enum.value.add(name="SECOND", number=7)
    message = proto.message_type.add(name="Options")
    message.extension_range.add(start=100, end=200)
    cases = [
        ("enabled", 8, "true"),
        ("count", 5, "42"),
        ("ratio", 2, "1.25"),
        ("text", 9, "hello"),
        ("data", 12, r"\001\377"),
        ("state", 14, "SECOND"),
    ]
    for number, (name, kind, default) in enumerate(cases, 1):
        for field in (
            message.field.add(name=name, number=number, label=1, type=kind, default_value=default),
            proto.extension.add(
                name="ext_" + name,
                number=number + 100,
                label=1,
                type=kind,
                default_value=default,
                extendee=".audit.defaults.Options",
            ),
        ):
            if kind == 14:
                field.type_name = ".audit.defaults.State"
    pool = descriptor_pool.DescriptorPool()
    pool.Add(proto)
    reference_type = message_factory.GetMessageClass(pool.FindMessageTypeByName("audit.defaults.Options"))
    register_file(proto.name, proto.SerializeToString())
    state = enum_class("audit.defaults.State", "State", {"FIRST": 5, "SECOND": 7})
    direct_type = message_class("audit.defaults.Options", "Options", {name: name for name, _, _ in cases})
    for direct in (direct_type(), direct_type.FromString(b"")):
        reference = reference_type()
        for name, kind, _ in cases:
            value = getattr(direct, name)
            expected = getattr(reference, name)
            assert value == expected
            if kind == 14:
                assert isinstance(value, state)
            assert not direct.HasField(name)
            handle = extension("audit.defaults.ext_" + name)
            assert direct.get_extension(handle) == reference.Extensions[pool.FindExtensionByName(handle.full_name)]
            assert not direct.has_extension(handle)
        assert direct.SerializeToString() == b""
        direct.enabled = True
        assert direct.HasField("enabled")
        assert direct.SerializeToString() == b"\x08\x01"


def test_documented_credential_examples_construct(monkeypatch):
    from nebius import sdk as sdk_module
    from nebius.aio.authorization.authorization import Provider
    from nebius.aio.token.file_cache.renewable_bearer import RenewableFileCacheBearer

    captured = []
    monkeypatch.setattr(sdk_module, "SDK", lambda **kwargs: captured.append(kwargs["credentials"]))
    for cls in (RenewableFileCacheBearer, Provider):
        example = cls.__doc__.split("::", 1)[1]
        namespace = Provider.__module__.split(".aio.")[0]
        exec(dedent(example).replace("from nebius.", f"from {namespace}."), {})
    assert len(captured) == 2
    assert captured[0]._bearer.name == "heavy-load-bearer"
    captured[1].authenticator()


@pytest.mark.asyncio()
async def test_synchronous_renewal_replaces_unshared_background_attempt(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_module, "DEFAULT_CONFIG_DIR", tmp_path)
    bearer = AsynchronousRenewableFileCacheBearer(NamedBearer(Bearer("unused"), "handoff"))
    started, blocked = asyncio.Event(), asyncio.Event()
    calls = 0

    async def fetch(timeout=None, options=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await blocked.wait()
        return Token("replacement")

    monkeypatch.setattr(
        bearer._source.receiver().__class__, "_fetch", lambda self, *args, **kwargs: fetch(*args, **kwargs)
    )
    background_waiter = asyncio.create_task(bearer.fetch(2))
    synchronous_waiter = None
    try:
        await asyncio.wait_for(started.wait(), 1)
        synchronous_waiter = asyncio.create_task(
            bearer.fetch(2, {OPTION_RENEW_REQUIRED: "1", OPTION_RENEW_SYNCHRONOUS: "1"})
        )
        assert (await synchronous_waiter).token == "replacement"
        assert (await background_waiter).token == "replacement"
        assert calls == 2
    finally:
        for task in (background_waiter, synchronous_waiter):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *(task for task in (background_waiter, synchronous_waiter) if task is not None), return_exceptions=True
        )
        await bearer.close()


@pytest.mark.asyncio()
async def test_memory_renewal_synchronous_waiter_joins_reported_attempt(monkeypatch):
    from nebius.aio.token.renewable import Bearer as RenewableBearer

    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def fetch(timeout=None, options=None):
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return Token("shared")

    bearer = RenewableBearer(Bearer("unused"))
    monkeypatch.setattr(
        bearer._source.receiver().__class__, "_fetch", lambda self, *args, **kwargs: fetch(*args, **kwargs)
    )
    first = asyncio.create_task(bearer.fetch(2, {OPTION_REPORT_ERROR: "1"}))
    second = None
    try:
        await asyncio.wait_for(started.wait(), 1)
        second = asyncio.create_task(bearer.fetch(2, {OPTION_RENEW_SYNCHRONOUS: "1"}))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second)
        assert [token.token for token in results] == ["shared", "shared"]
        assert calls == 1
    finally:
        release.set()
        for task in (first, second):
            if task is not None:
                task.cancel()
        await asyncio.gather(*(task for task in (first, second) if task is not None), return_exceptions=True)
        await bearer.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize("exponent", [2, 1e200])
async def test_memory_renewal_backoff_caps_and_resets(monkeypatch, exponent):
    from nebius.aio.token import renewable as renewal_module
    from nebius.aio.token.renewable import Bearer as RenewableBearer

    bearer = RenewableBearer(
        Bearer("unused"),
        initial_retry_timeout=timedelta(seconds=1),
        retry_timeout_exponent=exponent,
        max_retry_timeout=timedelta(seconds=3),
    )
    delays, attempts = [], []
    outcomes = iter([False, False, False, True, False, True])

    async def sleep(delay):
        delays.append(delay)

    async def fetch(timeout=None, options=None):
        attempts.append(bearer._renewal_attempt)
        if not next(outcomes):
            raise RuntimeError("source failed")
        if len(attempts) == 6:
            bearer.stop()
        return Token("renewed")

    monkeypatch.setattr(renewal_module, "sleep", sleep)
    monkeypatch.setattr(
        bearer._source.receiver().__class__, "_fetch", lambda self, *args, **kwargs: fetch(*args, **kwargs)
    )
    try:
        await asyncio.wait_for(bearer._run(), 2)
        assert delays[:3] == [1, min(exponent, 3), 3]
        assert delays[4] == 1
        assert attempts == [1, 2, 3, 4, 1, 2]
        assert bearer._renewal_attempt == 0
    finally:
        await bearer.close()
