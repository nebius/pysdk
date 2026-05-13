import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from nebius.aio.channel import Channel, NoCredentials
from nebius.aio.cli_config import Config
from nebius.aio.keepalive import (
    DEFAULT_KEEPALIVE_PERMIT_WITHOUT_STREAM,
    DEFAULT_KEEPALIVE_TIME_MS,
    DEFAULT_KEEPALIVE_TIMEOUT_MS,
    ENV_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM,
    ENV_GRPC_KEEPALIVE_TIME,
    ENV_GRPC_KEEPALIVE_TIMEOUT,
    KeepaliveOptions,
)
from nebius.aio.token.token import Token
from nebius.base.metadata import Metadata
from nebius.base.options import INSECURE
from nebius.sdk import SDK

KEEPALIVE_ENV = (
    ENV_GRPC_KEEPALIVE_TIME,
    ENV_GRPC_KEEPALIVE_TIMEOUT,
    ENV_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM,
)


def _option_map(options: list[tuple[str, object]]) -> dict[str, object]:
    return dict(options)


def _clear_keepalive_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in KEEPALIVE_ENV:
        monkeypatch.delenv(name, raising=False)


def _provider_name(cls: type[object]) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def test_keepalive_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_keepalive_env(monkeypatch)
    channel = Channel(options=[(INSECURE, True)], credentials=NoCredentials())
    opts = _option_map(channel.get_address_options("127.0.0.1:1"))

    assert opts["grpc.keepalive_time_ms"] == DEFAULT_KEEPALIVE_TIME_MS
    assert opts["grpc.keepalive_timeout_ms"] == DEFAULT_KEEPALIVE_TIMEOUT_MS
    assert opts["grpc.keepalive_permit_without_calls"] == (
        1 if DEFAULT_KEEPALIVE_PERMIT_WITHOUT_STREAM else 0
    )


def test_keepalive_env_and_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_keepalive_env(monkeypatch)
    monkeypatch.setenv(ENV_GRPC_KEEPALIVE_TIME, "45s")
    monkeypatch.setenv(ENV_GRPC_KEEPALIVE_TIMEOUT, "12s")
    monkeypatch.setenv(ENV_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM, "false")

    channel = Channel(options=[(INSECURE, True)], credentials=NoCredentials())
    opts = _option_map(channel.get_address_options("127.0.0.1:1"))
    assert opts["grpc.keepalive_time_ms"] == 45_000
    assert opts["grpc.keepalive_timeout_ms"] == 12_000
    assert opts["grpc.keepalive_permit_without_calls"] == 0

    disabled = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
        keepalive=False,
    )
    disabled_opts = _option_map(disabled.get_address_options("127.0.0.1:1"))
    assert "grpc.keepalive_time_ms" not in disabled_opts

    zero_time = Channel(
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
        keepalive=KeepaliveOptions(time_ms=0, timeout_ms=0),
    )
    zero_opts = _option_map(zero_time.get_address_options("127.0.0.1:1"))
    assert "grpc.keepalive_time_ms" not in zero_opts


def test_keepalive_user_options_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_keepalive_env(monkeypatch)
    channel = Channel(
        options=[(INSECURE, True), ("grpc.keepalive_time_ms", 5)],
        credentials=NoCredentials(),
    )
    opts = _option_map(channel.get_address_options("127.0.0.1:1"))
    assert opts["grpc.keepalive_time_ms"] == 5


def test_keepalive_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_keepalive_env(monkeypatch)
    monkeypatch.setenv(ENV_GRPC_KEEPALIVE_TIMEOUT, "0")
    with pytest.raises(ValueError, match="must be positive"):
        Channel(options=[(INSECURE, True)], credentials=NoCredentials())

    monkeypatch.setenv(ENV_GRPC_KEEPALIVE_TIMEOUT, "-1s")
    with pytest.raises(ValueError, match="must not be negative"):
        Channel(options=[(INSECURE, True)], credentials=NoCredentials())


@pytest.mark.asyncio
async def test_static_token_metrics() -> None:
    from nebius.aio.token.static import Bearer as StaticBearer

    acquired = []
    lifetimes = []
    metrics = {
        "token_acquire": acquired.append,
        "token_lifetime": lifetimes.append,
    }
    token = Token(
        "test-token",
        datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    sdk = SDK(options=[(INSECURE, True)], credentials=token, metrics=metrics)
    metadata = Metadata()

    await sdk.get_authorization_provider().authenticator().authenticate(metadata)  # type: ignore[union-attr]

    assert metadata.get_one("authorization") == "Bearer test-token"
    assert len(acquired) == 1
    assert acquired[0].provider == _provider_name(StaticBearer)
    assert acquired[0].result == "success"
    assert acquired[0].attempt == 1
    assert len(lifetimes) == 1
    assert lifetimes[0].provider == _provider_name(StaticBearer)
    assert 0 < lifetimes[0].ttl_seconds <= 60


@pytest.mark.asyncio
async def test_custom_bearer_metrics_provider_defaults_to_class_name() -> None:
    from nebius.aio.token.token import Bearer, Receiver

    class CustomReceiver(Receiver):
        async def _fetch(
            self,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> Token:
            return Token("custom-token")

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            return False

    class CustomBearer(Bearer):
        def receiver(self) -> Receiver:
            return CustomReceiver()

    acquired = []
    sdk = SDK(
        options=[(INSECURE, True)],
        credentials=CustomBearer(),
        metrics={"token_acquire": acquired.append},
    )
    metadata = Metadata()

    await sdk.get_authorization_provider().authenticator().authenticate(metadata)  # type: ignore[union-attr]

    assert metadata.get_one("authorization") == "Bearer custom-token"
    assert [(item.provider, item.result) for item in acquired] == [
        (_provider_name(CustomBearer), "success")
    ]


@pytest.mark.asyncio
async def test_non_token_receiver_result_records_error_metric() -> None:
    from nebius.aio.token.token import Bearer, Receiver

    class BadReceiver(Receiver):
        async def _fetch(
            self,
            timeout: float | None = None,
            options: dict[str, str] | None = None,
        ) -> Token:
            return object()  # type: ignore[return-value]

        def can_retry(
            self,
            err: Exception,
            options: dict[str, str] | None = None,
        ) -> bool:
            return False

    class BadBearer(Bearer):
        def receiver(self) -> Receiver:
            return BadReceiver()

    acquired = []
    sdk = SDK(
        options=[(INSECURE, True)],
        credentials=BadBearer(),
        metrics={"token_acquire": acquired.append},
    )

    with pytest.raises(TypeError, match="Expected Token"):
        await sdk.get_authorization_provider().authenticator().authenticate(Metadata())  # type: ignore[union-attr]

    assert [(item.provider, item.result) for item in acquired] == [
        (_provider_name(BadBearer), "error")
    ]


@pytest.mark.asyncio
async def test_naive_token_expiration_does_not_break_metrics() -> None:
    lifetimes = []
    sdk = SDK(
        options=[(INSECURE, True)],
        credentials=Token("test-token", datetime.now()),
        metrics={"token_lifetime": lifetimes.append},
    )
    metadata = Metadata()

    await sdk.get_authorization_provider().authenticator().authenticate(metadata)  # type: ignore[union-attr]

    assert metadata.get_one("authorization") == "Bearer test-token"
    assert lifetimes == []


@pytest.mark.asyncio
async def test_metric_cancelled_error_does_not_break_auth() -> None:
    def raise_cancelled_error(metric) -> None:
        raise asyncio.CancelledError()

    sdk = SDK(
        options=[(INSECURE, True)],
        credentials=Token("test-token"),
        metrics={"token_acquire": raise_cancelled_error},
    )
    metadata = Metadata()

    await sdk.get_authorization_provider().authenticator().authenticate(metadata)  # type: ignore[union-attr]

    assert metadata.get_one("authorization") == "Bearer test-token"


@pytest.mark.asyncio
async def test_token_file_metrics(tmp_path) -> None:
    from nebius.aio.token.file import Bearer as FileBearer

    token_file = tmp_path / "token.txt"
    token_file.write_text("file-token")
    acquired = []
    hits = []
    misses = []
    metrics = {
        "cache_hit": hits.append,
        "cache_miss": misses.append,
        "token_acquire": acquired.append,
    }
    sdk = SDK(
        options=[(INSECURE, True)],
        credentials=FileBearer(token_file),
        metrics=metrics,
    )

    first = Metadata()
    second = Metadata()
    await sdk.get_authorization_provider().authenticator().authenticate(first)  # type: ignore[union-attr]
    await sdk.get_authorization_provider().authenticator().authenticate(second)  # type: ignore[union-attr]

    assert first.get_one("authorization") == "Bearer file-token"
    assert second.get_one("authorization") == "Bearer file-token"
    assert [(item.provider, item.result) for item in acquired] == [("file", "success")]
    assert [(item.provider, item.result) for item in misses] == [("file", "success")]
    assert [item.provider for item in hits] == ["file"]


@pytest.mark.asyncio
async def test_token_file_retry_invalidates_cache_when_file_changes(tmp_path) -> None:
    from nebius.aio.token.file import Bearer as FileBearer

    token_file = tmp_path / "token.txt"
    token_file.write_text("old-token")
    invalidations = []
    misses = []
    metrics = {
        "cache_invalidate": invalidations.append,
        "cache_miss": misses.append,
    }
    bearer = FileBearer(token_file, refresh_period=5 * 60, metrics=metrics)
    receiver = bearer.receiver()

    first = await receiver.fetch()
    token_file.write_text("new-token")

    assert first.token == "old-token"
    assert receiver.can_retry(Exception("unauthenticated")) is True
    assert [item.provider for item in invalidations] == ["file"]

    second = await receiver.fetch()

    assert second.token == "new-token"
    assert [(item.provider, item.result) for item in misses] == [
        ("file", "success"),
        ("file", "success"),
    ]


def test_config_reader_metrics_replay_and_credentials_resolve(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "default: test",
                "profiles:",
                "  test:",
                "    endpoint: api.example.test:443",
                "    token-file: /tmp/nebius-token",
            ]
        )
    )
    events = []
    metrics = {
        "config_load": lambda metric: events.append(("config_load", metric)),
        "credentials_resolve": lambda metric: events.append(
            ("credentials_resolve", metric)
        ),
    }

    config = Config(config_file=config_file, no_env=True)
    SDK(
        options=[(INSECURE, True)],
        config_reader=config,
        metrics=metrics,
    )

    assert ("config_load", "file", "success") in {
        (kind, metric.source, metric.result) for kind, metric in events
    }
    assert ("credentials_resolve", "token-file", "success") in {
        (kind, metric.source, metric.result) for kind, metric in events
    }


def test_async_config_metric_callback_runs_from_sync_constructor(tmp_path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "default: test",
                "profiles:",
                "  test:",
                "    endpoint: api.example.test:443",
                "    token-file: /tmp/nebius-token",
            ]
        )
    )
    events = []

    async def config_load(metric) -> None:
        await asyncio.sleep(0)
        events.append(("config_load", metric.source, metric.result))

    Config(
        config_file=config_file,
        no_env=True,
        metrics={"config_load": config_load},
    )

    assert events == [("config_load", "file", "success")]


@pytest.mark.asyncio
async def test_config_reader_env_credentials_keep_auth_metrics(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nebius.aio.token.static import EnvBearer

    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "default: test",
                "profiles:",
                "  test:",
                "    endpoint: api.example.test:443",
            ]
        )
    )
    acquired = []
    monkeypatch.setenv("NEBIUS_TEST_TOKEN", "env-token")

    config = Config(
        config_file=config_file,
        token_env="NEBIUS_TEST_TOKEN",
        metrics={"token_acquire": acquired.append},
    )
    credentials = config.get_credentials(None)  # type: ignore[arg-type]
    token = await credentials.receiver().fetch()  # type: ignore[attr-defined]

    assert token.token == "env-token"
    assert [(item.provider, item.result) for item in acquired] == [
        (_provider_name(EnvBearer), "success")
    ]


def test_config_reader_metrics_replay_excludes_prior_credentials_resolve(
    tmp_path,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "\n".join(
            [
                "default: test",
                "profiles:",
                "  test:",
                "    endpoint: api.example.test:443",
                "    token-file: /tmp/nebius-token",
            ]
        )
    )
    events = []

    config = Config(config_file=config_file, no_env=True)
    config.get_credentials(None)  # type: ignore[arg-type]
    config.set_metrics(
        {
            "config_load": lambda metric: events.append(("config_load", metric)),
            "credentials_resolve": lambda metric: events.append(
                ("credentials_resolve", metric)
            ),
        }
    )

    assert ("config_load", "file", "success") in {
        (kind, metric.source, metric.result) for kind, metric in events
    }
    assert [
        (kind, metric.source, metric.result)
        for kind, metric in events
        if kind == "credentials_resolve"
    ] == []
