"""Check public IMDS credentials and endpoint diagnostics."""

from asyncio import Event, TimeoutError, create_task, sleep, wait_for
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from aiohttp import ClientPayloadError, StreamReader, web
from nebius.aio.cli_config import Config
from nebius.aio.token.imds import Bearer, IMDSError
from nebius.aio.token.impersonated import CachedBearer as ImpersonatedBearer


@asynccontextmanager
async def token_endpoint(responses):
    """Serve deterministic token responses without external IAM credentials."""
    requests = []

    async def handle(request):
        requests.append(request.headers.get("Metadata"))
        status, body = responses[min(len(requests) - 1, len(responses) - 1)]
        return web.Response(status=status, body=body)

    app = web.Application()
    app.router.add_get("/token", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}/token", requests
    finally:
        await runner.cleanup()


@pytest.mark.asyncio()
async def test_public_config_imds_retries_and_reports_metrics(tmp_path) -> None:
    body = b'{"access_token":"actor-token","expires_at":"2099-01-01T00:00:00Z"}'
    error_body = b"credential-secret" + b"x" * 65537
    async with token_endpoint([(500, error_body), (429, error_body), (200, body)]) as (endpoint, requests):
        profile = tmp_path / "config.yaml"
        profile.write_text(f"default: vm\nprofiles:\n  vm:\n    token-endpoint: {endpoint}\n")
        metrics = []
        config = Config(config_file=profile, no_env=True, auth_metrics={"token_acquire": metrics.append})
        credentials = config.get_credentials(object())
        token = await credentials.receiver().fetch(timeout=2)
        assert token.token == "actor-token"
        assert token.expiration == datetime(2099, 1, 1, tzinfo=timezone.utc)
        assert requests == ["true", "true", "true"]
        assert len(metrics) == 1 and metrics[0].attempt == 3


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "status,body,expected",
    [
        (200, b'{"access_token":"credential-secret", invalid}', "could not decode"),
        (200, b'{"access_token":"token"}', "expires_at"),
        (200, b'{"access_token":"token","expires_at":"credential-secret"}', "expires_at"),
        (200, b'{"access_token":"","expires_at":"2099-01-01T00:00:00Z"}', "access_token"),
        (200, b"x" * 65537, "65536 bytes"),
    ],
)
async def test_imds_response_validation_and_redaction(status, body, expected) -> None:
    async with token_endpoint([(status, body)]) as (endpoint, requests):
        with pytest.raises(IMDSError, match=expected) as raised:
            await Bearer(endpoint).receiver().fetch(timeout=2)
        assert "credential-secret" not in str(raised.value)
        assert raised.value.__cause__ is None
        assert len(requests) == 1


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "status,body,expected,truncated",
    [
        (403, b"endpoint denied", "endpoint denied", False),
        (500, b"endpoint unavailable", "endpoint unavailable", False),
        (403, b"invalid \xff", "invalid \ufffd", False),
        (403, b"", "HTTP 403:", False),
        (403, b"prefix " + b"x" * 65537 + b"hidden-tail", "prefix ", True),
        (500, b"prefix " + b"x" * 65537 + b"hidden-tail", "prefix ", True),
    ],
    ids=["forbidden", "retry-exhausted", "invalid-utf8", "empty", "large-forbidden", "large-retry-exhausted"],
)
async def test_imds_http_error_includes_bounded_body(status, body, expected, truncated) -> None:
    async with token_endpoint([(status, body)]) as (endpoint, requests):
        with pytest.raises(IMDSError, match=f"HTTP {status}") as raised:
            await Bearer(endpoint).receiver().fetch(timeout=2)
        message = str(raised.value)
        assert expected in message
        assert message.endswith("... (truncated)") == truncated
        assert "hidden-tail" not in message
        assert len(message) < 65536 + 100
        assert len(requests) == (3 if status == 500 else 1)


@pytest.mark.asyncio()
@pytest.mark.parametrize("status", [403, 500])
async def test_imds_body_read_failure_preserves_http_status(monkeypatch, status) -> None:
    async def broken_read(reader, size):
        raise ClientPayloadError("incomplete response")

    monkeypatch.setattr(StreamReader, "readexactly", broken_read)
    async with token_endpoint([(status, b"endpoint error")]) as (endpoint, requests):
        with pytest.raises(IMDSError, match=f"HTTP {status}; could not read response body"):
            await Bearer(endpoint).receiver().fetch(timeout=2)
        assert len(requests) == (3 if status == 500 else 1)


@pytest.mark.asyncio()
async def test_imds_timeout_covers_http_retries() -> None:
    async with token_endpoint([(500, b"retry")]) as (endpoint, requests):
        with pytest.raises(TimeoutError):
            await Bearer(endpoint).receiver().fetch(timeout=0.01)
        assert len(requests) <= 1


@pytest.mark.asyncio()
async def test_imds_config_can_wrap_impersonation(tmp_path) -> None:
    from nebius.api.nebius.iam.v1 import CreateTokenResponse

    body = b'{"access_token":"actor-token","expires_at":"2099-01-01T00:00:00Z"}'
    async with token_endpoint([(200, body)]) as (endpoint, requests):
        profile = tmp_path / "config.yaml"
        profile.write_text(
            f"default: vm\nprofiles:\n  vm:\n    token-endpoint: {endpoint}\n"
            "    impersonate-service-account-id: serviceaccount-target\n",
        )
        config = Config(config_file=profile, no_env=True)
        credentials = config.get_credentials(object())
        assert isinstance(credentials, ImpersonatedBearer)

        class Exchange:
            async def exchange(self, request, **kwargs):
                assert request.actor_token == "actor-token"
                assert request.subject_token == "serviceaccount-target"
                assert kwargs["auth_options"]["type"] == "disable"
                return CreateTokenResponse(access_token="impersonated-token", token_type="Bearer", expires_in=3600)

        credentials._impersonated._svc = Exchange()
        try:
            token = await credentials.receiver().fetch(timeout=2)
            assert token.token == "impersonated-token"
            assert requests == ["true"]
        finally:
            await credentials.close()


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "suffix_kind",
    ["valid", "oversized", "invalid", "timeout", "http-error", "http-error-timeout"],
)
async def test_imds_reads_complete_streamed_body(monkeypatch, suffix_kind) -> None:
    """Read all chunks and enforce validation before returning a token."""
    complete = b'{"access_token":"actor-token","expires_at":"2099-01-01T00:00:00Z"}'
    if suffix_kind.startswith("http-error"):
        prefix, suffix = b"first chunk", b"; last chunk"
    elif suffix_kind in ("valid", "timeout"):
        prefix, suffix = complete[:20], complete[20:]
    else:
        prefix = complete
        suffix = b" " * 65536 if suffix_kind == "oversized" else b"invalid"
    delivered = Event()
    release_suffix = Event()
    original_feed_data = StreamReader.feed_data
    received = bytearray()

    def feed_data(reader, data, size=0):
        original_feed_data(reader, data, size)
        received.extend(data)
        if received == prefix:
            delivered.set()

    monkeypatch.setattr(StreamReader, "feed_data", feed_data)

    async def handle(request):
        response = web.StreamResponse(status=403 if suffix_kind.startswith("http-error") else 200)
        await response.prepare(request)
        await response.write(prefix)
        await release_suffix.wait()
        try:
            await response.write(suffix)
            await response.write_eof()
        except ConnectionResetError:
            pass
        return response

    app = web.Application()
    app.router.add_get("/token", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    timeout = 2
    fetch = create_task(Bearer(f"http://127.0.0.1:{port}/token").receiver().fetch(timeout=timeout))
    try:
        await wait_for(delivered.wait(), timeout=2)
        await sleep(0)
        if suffix_kind in ("timeout", "http-error-timeout"):
            with pytest.raises(TimeoutError):
                await fetch
        else:
            assert not fetch.done(), "Wait for the remaining response bytes."
            release_suffix.set()
            if suffix_kind == "valid":
                assert (await fetch).token == "actor-token"
            elif suffix_kind == "http-error":
                with pytest.raises(IMDSError, match="HTTP 403: first chunk; last chunk"):
                    await fetch
            else:
                message = "65536 bytes" if suffix_kind == "oversized" else "could not decode"
                with pytest.raises(IMDSError, match=message):
                    await fetch
    finally:
        release_suffix.set()
        if not fetch.done():
            fetch.cancel()
        await runner.cleanup()
