# type: ignore

import pytest

from nebius.aio import request

request.DEFAULT_AUTH_TIMEOUT = 5.0


def test_load_config_from_home(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
""")
    # Load the configuration
    config = Config("foo")
    assert config.parent_id == "project-e00some-id"


@pytest.mark.asyncio
async def test_load_config_env_token(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface
    from nebius.aio.cli_config import Config
    from nebius.aio.token.static import EnvBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NEBIUS_IAM_TOKEN", "my-token")

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
""")
    # Load the configuration
    config = Config("foo")
    fut = Future[ClientChannelInterface]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, EnvBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


@pytest.mark.asyncio
async def test_load_config_token_file(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface
    from nebius.aio.cli_config import Config
    from nebius.aio.token.file import Bearer as FileBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("NEBIUS_IAM_TOKEN", raising=False)

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        token-file: ~/token.txt
""")
    with open(tmp_path / "token.txt", "w+") as f:
        f.write("my-token")
    # Load the configuration
    config = Config("foo")
    fut = Future[ClientChannelInterface]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, FileBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


@pytest.mark.asyncio
async def test_impersonated_bearer_exchange_request() -> None:
    from nebius.aio.token.impersonated import Receiver as ImpersonatedReceiver
    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.api.nebius.iam.v1 import (
        CreateTokenResponse,
        ExchangeTokenRequest,
    )

    seen: list[ExchangeTokenRequest] = []

    class TokenExchange:
        async def exchange(self, request, **kwargs):
            seen.append(request)
            assert kwargs["auth_options"]["type"] == "disable"
            return CreateTokenResponse(
                access_token="impersonated-token",
                token_type="Bearer",
                expires_in=3600,
            )

    receiver = ImpersonatedReceiver(
        "target-sa",
        StaticBearer("actor-token").receiver(),
        TokenExchange(),  # type: ignore[arg-type]
    )
    token = await receiver.fetch()
    assert token.token == "impersonated-token"
    assert len(seen) == 1
    request = seen[0]
    assert request.grant_type == "urn:ietf:params:oauth:grant-type:token-exchange"
    assert (
        request.requested_token_type == "urn:ietf:params:oauth:token-type:access_token"
    )
    assert request.subject_token == "target-sa"
    assert (
        request.subject_token_type
        == "urn:nebius:params:oauth:token-type:subject_identifier"
    )
    assert request.actor_token == "actor-token"
    assert request.actor_token_type == "urn:ietf:params:oauth:token-type:access_token"


@pytest.mark.asyncio
async def test_config_impersonates_with_constructor_override(
    tmp_path, monkeypatch
) -> None:
    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface
    from nebius.aio.cli_config import Config
    from nebius.aio.token.impersonated import CachedBearer as ImpersonatedBearer

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("NEBIUS_IAM_TOKEN", raising=False)
    cfg_dir = home / ".nebius"
    cfg_dir.mkdir(parents=True)
    token_file = cfg_dir / "token.txt"
    token_file.write_text("actor-token")
    config_file = cfg_dir / "config.yaml"
    config_file.write_text(
        f"""
default: prod
profiles:
  prod:
    endpoint: example.net
    parent-id: project-id
    token-file: {token_file}
    impersonate-service-account-id: profile-sa
""",
    )

    config = Config(
        "foo",
        config_file=config_file,
        no_env=True,
        impersonate_service_account_id="override-sa",
    )
    credentials = config.get_credentials(Future[ClientChannelInterface]())
    assert isinstance(credentials, ImpersonatedBearer)
    assert credentials.name is not None
    assert "override-sa" in credentials.name
    assert "profile-sa" not in credentials.name


@pytest.mark.asyncio
async def test_load_config_no_env(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface
    from nebius.aio.cli_config import Config
    from nebius.aio.token.file import Bearer as FileBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NEBIUS_IAM_TOKEN", "wrong-token")

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        token-file: ~/token.txt
""")
    with open(tmp_path / "token.txt", "w+") as f:
        f.write("my-token")
    # Load the configuration
    config = Config("foo", no_env=True)
    fut = Future[ClientChannelInterface]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, FileBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


def test_load_config_other_profile(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
    test:
        endpoint: test-endpoint.net
        parent-id: project-e00test-id
""")
    # Load the configuration
    config = Config("foo", profile="test")
    assert config.parent_id == "project-e00test-id"


def test_load_config_no_project(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
""")
    # Load the configuration
    config = Config("foo")
    try:
        config.parent_id
    except Exception as e:
        assert str(e) == "Missing parent-id in the profile."


def test_load_config_from_home_fail(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    try:
        Config("foo")
    except FileNotFoundError as e:
        assert str(e).startswith("Config file ")
        assert str(e).endswith("/.nebius/config.yaml not found.")


def test_load_config_from_other_place(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / "home/.nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_path / "config.yaml"

    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    with open(tmp_file, "w+") as f:
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
""")
    # Load the configuration
    config = Config("foo", config_file=str(tmp_file))
    assert config.parent_id == "project-e00some-id"


@pytest.mark.asyncio
async def test_load_config_federated_subject_file(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config
    from nebius.aio.token.federated_credentials import FederatedCredentialsBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    actor_file = tmp_path / "actor.txt"
    actor_file.write_text("actor-token")

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(f"""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        auth-type: service account
        service-account-id: sa-actor
        federated-subject-credentials-file-path: {actor_file}
""")

    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface

    config = Config("foo")
    fut = Future[ClientChannelInterface]()
    cred = config.get_credentials(fut)
    assert isinstance(cred, FederatedCredentialsBearer)


@pytest.mark.asyncio
async def test_load_config_service_account_credentials_file(
    tmp_path, monkeypatch
) -> None:
    # create a service account credentials JSON with a PEM private key
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from nebius.aio.cli_config import Config
    from nebius.aio.token.service_account import ServiceAccountBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    # generate key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    import json

    cred_file = tmp_path / "sa_creds.json"
    cred_file.write_text(
        json.dumps(
            {
                "subject-credentials": {
                    "type": "JWT",
                    "alg": "RS256",
                    "private-key": pem,
                    "kid": "kid-1",
                    "iss": "sa-creds",
                    "sub": "sa-creds",
                }
            }
        )
    )

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(f"""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        auth-type: service account
        service-account-credentials-file-path: {cred_file}
""")

    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface

    config = Config("foo")
    fut = Future[ClientChannelInterface]()
    cred = config.get_credentials(fut)
    assert isinstance(cred, ServiceAccountBearer)


@pytest.mark.asyncio
async def test_load_config_private_key_file(tmp_path, monkeypatch) -> None:
    # Test private-key-file-path
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from nebius.aio.cli_config import Config
    from nebius.aio.token.service_account import ServiceAccountBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    # generate key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    pem_file = tmp_path / "pk.pem"
    pem_file.write_text(pem)

    # first test private-key-file-path
    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(f"""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        auth-type: service account
        service-account-id: sa-file
        public-key-id: kid-file
        private-key-file-path: {pem_file}
""")
    config = Config("foo")
    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface

    fut = Future[ClientChannelInterface]()
    cred = config.get_credentials(fut)
    assert isinstance(cred, ServiceAccountBearer)


@pytest.mark.asyncio
async def test_load_config_private_key_inline(tmp_path, monkeypatch) -> None:
    # Test inline private-key branch
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from nebius.aio.cli_config import Config
    from nebius.aio.token.service_account import ServiceAccountBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    # generate key
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    pem_file = tmp_path / "pk.pem"
    pem_file.write_text(pem)
    # now inline private-key
    with open(nebius_dir / "config.yaml", "w+") as f:
        # indent PEM as YAML literal
        pem_block = "\n".join(["            " + line for line in pem.splitlines()])
        f.write("""
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        auth-type: service account
        service-account-id: sa-inline
        public-key-id: kid-inline
        private-key: |
""" + pem_block)
    config = Config("foo")
    from asyncio import Future

    from nebius.aio.abc import ClientChannelInterface

    fut = Future[ClientChannelInterface]()
    cred = config.get_credentials(fut)
    assert isinstance(cred, ServiceAccountBearer)
