# type: ignore
import pytest

from nebius.aio import request

request.DEFAULT_AUTH_TIMEOUT = 5.0


@pytest.mark.asyncio
async def test_env_and_token_file_auth(monkeypatch, tmp_path) -> None:
    """Verify EnvBearer and FileBearer via Config + SDK on a compute call."""
    import grpc
    import grpc.aio

    from nebius.aio.cli_config import Config
    from nebius.api.nebius.compute.v1 import (
        DiskServiceClient,
    )
    from nebius.api.nebius.compute.v1 import (
        ListDisksRequest as V1List,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2 import ListDisksResponse
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE
    from nebius.sdk import SDK

    class Compute(DiskServiceServicer):
        def __init__(self, expected_token: str) -> None:
            self.expected_token = expected_token

        async def List(self, request, context):  # noqa: N802 — GRPC method
            headers = dict(context.invocation_metadata() or [])
            auth = headers.get("authorization", "")
            assert self.expected_token in auth
            return ListDisksResponse(items=[])

    async def run_case(expected_token: str, cfg_yaml: str) -> None:
        srv = grpc.aio.server()
        port = srv.add_insecure_port("[::]:0")
        add_DiskServiceServicer_to_server(Compute(expected_token), srv)
        await srv.start()
        try:
            home = (tmp_path / "home_env").resolve()
            monkeypatch.setenv("HOME", str(home))
            cfg_dir = home / ".nebius"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / "config.yaml"
            cfg_file.write_text(cfg_yaml)

            sdk = SDK(
                domain=f"localhost:{port}",
                options=[(INSECURE, True)],
                config_reader=Config(
                    config_file=cfg_file,
                    profile="test",
                    no_env=True,
                ),
            )
            try:
                client = DiskServiceClient(sdk)
                await client.list(V1List())
            finally:
                await sdk.close()
        finally:
            await srv.stop(0)

    # Env token case: ensure get_token() reads env when no_env not set
    env_home = (tmp_path / "env_home").resolve()
    monkeypatch.setenv("HOME", str(env_home))
    monkeypatch.setenv("NEBIUS_IAM_TOKEN", "envtok")
    cfg_env_dir = env_home / ".nebius"
    cfg_env_dir.mkdir(parents=True, exist_ok=True)
    (cfg_env_dir / "config.yaml").write_text(
        """
default: test
profiles:
  test:
    auth-type: service account
    endpoint: some.endpoint
""".strip()
    )
    sdk1 = SDK(
        domain="localhost:0",
        options=[(INSECURE, True)],
        config_reader=Config(
            config_file=cfg_env_dir / "config.yaml",
            profile="test",
        ),
    )
    try:
        tok = await sdk1.get_token(timeout=2.0, options=None)
        assert tok.token == "envtok"
    finally:
        await sdk1.close()

    # Token-file case
    tok_dir = tmp_path / "tok"
    tok_dir.mkdir(parents=True, exist_ok=True)
    tok_file = tok_dir / "tok.txt"
    tok_file.write_text("filetok\n")
    cfg_yaml_file = f"""
default: test
profiles:
  test:
    token-file: {tok_file}
    endpoint: some.endpoint
""".strip()
    await run_case("filetok", cfg_yaml_file)


@pytest.mark.asyncio
async def test_service_account_variants(monkeypatch, tmp_path) -> None:
    """
    Service account via inline PEM, credentials file,
    and federated credentials file.
    """
    import grpc
    import grpc.aio
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from nebius.aio.cli_config import Config
    from nebius.api.nebius.compute.v1 import (
        DiskServiceClient,
    )
    from nebius.api.nebius.compute.v1 import (
        ListDisksRequest as V1List,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2 import ListDisksResponse
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc import (
        TokenExchangeService,
        add_TokenExchangeServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_service_pb2 import CreateTokenResponse
    from nebius.base.options import INSECURE
    from nebius.sdk import SDK

    class Compute(DiskServiceServicer):
        async def List(self, request, context):  # noqa: N802 — GRPC method
            headers = dict(context.invocation_metadata() or [])
            assert "satok" in headers.get("authorization", "")
            return ListDisksResponse(items=[])

    class TokenExchange(TokenExchangeService):
        async def Exchange(self, request, context):  # noqa: N802 — GRPC method
            return CreateTokenResponse(
                access_token="satok", token_type="Bearer", expires_in=3600
            )

    srv = grpc.aio.server()
    port = srv.add_insecure_port("[::]:0")
    add_DiskServiceServicer_to_server(Compute(), srv)
    add_TokenExchangeServiceServicer_to_server(TokenExchange(), srv)
    await srv.start()
    try:
        home = (tmp_path / "sa_home").resolve()
        monkeypatch.setenv("HOME", str(home))
        cfg_dir = home / ".nebius"
        cfg_dir.mkdir(parents=True, exist_ok=True)

        # Generate a test RSA key and PEM in PKCS8 format
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        # 1) Inline private key
        pem_block = "\n".join(["      " + ln for ln in pem.strip().splitlines()])
        cfg_inline = (
            "default: test\n"
            "profiles:\n"
            "  test:\n"
            "    auth-type: service account\n"
            "    service-account-id: sa-123\n"
            "    public-key-id: pk-abc\n"
            "    private-key: |-\n" + pem_block + f"\n    endpoint: localhost:{port}\n"
        )
        (cfg_dir / "config.yaml").write_text(cfg_inline)
        sdk = SDK(
            domain=f"localhost:{port}",
            options=[(INSECURE, True)],
            config_reader=Config(
                config_file=cfg_dir / "config.yaml",
                profile="test",
                no_env=True,
            ),
        )
        try:
            client = DiskServiceClient(sdk)
            await client.list(V1List())
        finally:
            await sdk.close()

        # 2) Credentials file path
        import json as _json

        creds_file = cfg_dir / "sa.json"
        creds_file.write_text(
            _json.dumps(
                {
                    "subject-credentials": {
                        "type": "JWT",
                        "alg": "RS256",
                        "private-key": pem,
                        "kid": "pk-abc",
                        "iss": "sa-123",
                        "sub": "sa-123",
                    }
                }
            )
        )
        cfg_creds = f"""
default: test
profiles:
  test:
    auth-type: service account
    service-account-credentials-file-path: {creds_file}
    endpoint: localhost:{port}
""".strip()
        (cfg_dir / "config.yaml").write_text(cfg_creds)
        sdk2 = SDK(
            domain=f"localhost:{port}",
            options=[(INSECURE, True)],
            config_reader=Config(
                config_file=cfg_dir / "config.yaml",
                profile="test",
                no_env=True,
            ),
        )
        try:
            client = DiskServiceClient(sdk2)
            await client.list(V1List())
        finally:
            await sdk2.close()

        # 3) Federated subject credentials file path
        fc_file = cfg_dir / "fc.txt"
        fc_file.write_text("federated-creds")
        cfg_fc = f"""
default: test
profiles:
  test:
    auth-type: service account
    service-account-id: sa-123
    federated-subject-credentials-file-path: {fc_file}
    endpoint: localhost:{port}
""".strip()
        (cfg_dir / "config.yaml").write_text(cfg_fc)
        sdk3 = SDK(
            domain=f"localhost:{port}",
            options=[(INSECURE, True)],
            config_reader=Config(
                config_file=cfg_dir / "config.yaml",
                profile="test",
                no_env=True,
            ),
        )
        try:
            client = DiskServiceClient(sdk3)
            await client.list(V1List())
        finally:
            await sdk3.close()
    finally:
        await srv.stop(0)


@pytest.mark.asyncio
async def test_federation_auth_flow(monkeypatch, tmp_path) -> None:
    """End-to-end federation flow against a local HTTP server, no browser open."""
    import asyncio
    import io
    import socket

    import aiohttp
    import grpc
    import grpc.aio
    from aiohttp import web

    from nebius.aio.cli_config import Config
    from nebius.api.nebius.compute.v1 import (
        DiskServiceClient,
    )
    from nebius.api.nebius.compute.v1 import (
        ListDisksRequest as V1List,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2 import ListDisksResponse
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE
    from nebius.sdk import SDK

    code_value = "authcode"
    token_value = "tok123"

    async def handle_authorize(request: web.Request) -> web.StreamResponse:
        q = request.rel_url.query
        state = q.get("state", "")
        redirect = q.get("redirect_uri", "")
        assert state and redirect
        location = f"{redirect}?code={code_value}&state={state}"
        raise web.HTTPFound(location=location)

    async def handle_token(request: web.Request) -> web.Response:
        data = await request.post()
        if data.get("code") != code_value:
            return web.Response(status=400, text="wrong code")
        return web.json_response({"access_token": token_value, "expires_in": 3600})

    app = web.Application()
    app.router.add_get("/oauth2/authorize", handle_authorize)
    app.router.add_post("/oauth2/token", handle_token)
    runner = web.AppRunner(app)
    await runner.setup()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    http_port = sock.getsockname()[1]
    sock.close()
    site = web.TCPSite(runner, "127.0.0.1", http_port)
    await site.start()
    try:
        fed_url = f"http://127.0.0.1:{http_port}"

        class Compute(DiskServiceServicer):
            async def List(self, request, context):  # noqa: N802 — GRPC method
                headers = dict(context.invocation_metadata() or [])
                assert token_value in headers.get("authorization", "")
                return ListDisksResponse(items=[])

        srv = grpc.aio.server()
        port = srv.add_insecure_port("[::]:0")
        add_DiskServiceServicer_to_server(Compute(), srv)
        await srv.start()
        try:
            home = (tmp_path / "fed_home").resolve()
            monkeypatch.setenv("HOME", str(home))
            cfg_dir = home / ".nebius"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file = cfg_dir / "config.yaml"
            cfg_file.write_text(
                f"""
default: test
profiles:
  test:
    auth-type: federation
    federation-endpoint: {fed_url}
    federation-id: fid-123
    endpoint: localhost:{port}
""".strip()
            )

            out = io.StringIO()
            sdk = SDK(
                domain=f"localhost:{port}",
                options=[(INSECURE, True)],
                config_reader=Config(
                    client_id="client-abc",
                    config_file=cfg_file,
                    profile="test",
                    no_env=True,
                ),
                federation_invitation_writer=out,
                federation_invitation_no_browser_open=True,
            )
            try:
                client = DiskServiceClient(sdk)

                async def follow_link() -> None:
                    import re

                    for _ in range(200):
                        s = out.getvalue()
                        m = re.search(r"https?://[^\s]+", s)
                        if m:
                            url = m.group(0)
                            async with aiohttp.ClientSession() as session:
                                try:
                                    await session.get(url, allow_redirects=True)
                                except Exception:
                                    pass
                            return
                        await asyncio.sleep(0.05)

                task = asyncio.create_task(follow_link())
                await client.list(V1List())
                await task
            finally:
                await sdk.close()
        finally:
            await srv.stop(0)
    finally:
        await runner.cleanup()
