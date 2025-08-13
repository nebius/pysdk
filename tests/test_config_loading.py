# type: ignore

import pytest


def test_load_config_from_home(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
"""
        )
    # Load the configuration
    config = Config("foo")
    assert config.parent_id == "project-e00some-id"


@pytest.mark.asyncio
async def test_load_config_env_token(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.base import ChannelBase
    from nebius.aio.cli_config import Config
    from nebius.aio.token.static import EnvBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NEBIUS_IAM_TOKEN", "my-token")

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
"""
        )
    # Load the configuration
    config = Config("foo")
    fut = Future[ChannelBase]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, EnvBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


@pytest.mark.asyncio
async def test_load_config_token_file(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.base import ChannelBase
    from nebius.aio.cli_config import Config
    from nebius.aio.token.file import Bearer as FileBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("NEBIUS_IAM_TOKEN", raising=False)

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        token-file: ~/token.txt
"""
        )
    with open(tmp_path / "token.txt", "w+") as f:
        f.write("my-token")
    # Load the configuration
    config = Config("foo")
    fut = Future[ChannelBase]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, FileBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


@pytest.mark.asyncio
async def test_load_config_no_env(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.base import ChannelBase
    from nebius.aio.cli_config import Config
    from nebius.aio.token.file import Bearer as FileBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NEBIUS_IAM_TOKEN", "wrong-token")

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        token-file: ~/token.txt
"""
        )
    with open(tmp_path / "token.txt", "w+") as f:
        f.write("my-token")
    # Load the configuration
    config = Config("foo", no_env=True)
    fut = Future[ChannelBase]()
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
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
    test:
        endpoint: test-endpoint.net
        parent-id: project-e00test-id
"""
        )
    # Load the configuration
    config = Config("foo", profile="test")
    assert config.parent_id == "project-e00test-id"


def test_load_config_no_project(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
"""
        )
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
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
"""
        )
    # Load the configuration
    config = Config("foo", config_file=str(tmp_file))
    assert config.parent_id == "project-e00some-id"
