from logging import getLogger
from os import environ
from os.path import isfile
from pathlib import Path
from ssl import SSLContext
from typing import Any, TextIO

from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
from nebius.aio.base import ChannelBase
from nebius.aio.token.service_account import ServiceAccountBearer
from nebius.aio.token.static import EnvBearer, NoTokenInEnvError
from nebius.aio.token.token import Bearer as TokenBearer
from nebius.aio.token.token import Token
from nebius.base.constants import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    PROFILE_ENV,
    TOKEN_ENV,
)
from nebius.base.error import SDKError
from nebius.base.service_account.service_account import (
    TokenRequester as TokenRequestReader,
)

Credentials = AuthorizationProvider | TokenBearer | TokenRequestReader | Token | str


log = getLogger(__name__)


class ConfigError(SDKError):
    pass


class NoParentIdError(ConfigError):
    pass


class Config:
    def __init__(
        self,
        client_id: str | None = None,
        config_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CONFIG_FILE,
        profile: str | None = None,
        profile_env: str = PROFILE_ENV,
        token_env: str = TOKEN_ENV,
        no_env: bool = False,
        no_parent_id: bool = False,
        max_retries: int = 2,
    ) -> None:
        self._client_id = client_id
        self._priority_bearer: EnvBearer | None = None
        self._profile_name = profile
        if not no_env:
            try:
                self._priority_bearer = EnvBearer(env_var_name=token_env)
            except NoTokenInEnvError:
                pass
            if self._profile_name is None:
                self._profile_name = environ.get(profile_env, None)
        self._no_parent_id = no_parent_id
        self._config_file = Path(config_file).expanduser()
        self._endpoint: str | None = None
        self._max_retries = max_retries
        self._get_profile()

    @property
    def parent_id(self) -> str:
        if self._no_parent_id:
            raise NoParentIdError(
                "Config is set to not use parent id from the profile."
            )
        if "parent-id" not in self._profile:
            raise NoParentIdError("Missing parent-id in the profile.")
        if not isinstance(self._profile["parent-id"], str):
            raise ConfigError(
                "Parent id should be a string, got "
                f"{type(self._profile['parent-id'])}."
            )
        if self._profile["parent-id"] == "":
            raise NoParentIdError("Parent id is empty.")

        return self._profile["parent-id"]

    def endpoint(self) -> str:
        return self._endpoint or ""

    def _get_profile(self) -> None:
        """Get the profile from the config file."""
        import yaml

        if not isfile(self._config_file):
            raise FileNotFoundError(f"Config file {self._config_file} not found.")

        with open(self._config_file, "r") as f:
            config = yaml.safe_load(f)

        if "profiles" not in config:
            raise ConfigError("No profiles found in the config file.")
        if not isinstance(config["profiles"], dict):
            raise ConfigError(
                f"Profiles should be a dictionary, got {type(config['profiles'])}."
            )
        if len(config["profiles"]) == 0:
            raise ConfigError(
                "No profiles found in the config file, setup the nebius CLI profile"
                " first."
            )
        if self._profile_name is None:
            if "default" not in config:
                if len(config["profiles"]) == 1:
                    self._profile_name = list(config["profiles"].keys())[0]
                else:
                    raise ConfigError("No default profile found in the config file.")
            else:
                self._profile_name = config["default"]
            if self._profile_name is None:
                raise ConfigError(
                    "No profile selected. Either set the profile in the config setup,"
                    " set the env var NEBIUS_PROFILE or "
                    "execute `nebius profile activate`."
                )
        profile = self._profile_name
        if not isinstance(profile, str):
            raise ConfigError(f"Profile name should be a string, got {type(profile)}.")
        if profile not in config["profiles"]:
            raise ConfigError(f"Profile {profile} not found in the config file.")
        if not isinstance(config["profiles"][profile], dict):
            raise ConfigError(
                f"Profile {profile} should be a dictionary, got "
                f"{type(config['profiles'][profile])}."
            )
        self._profile: dict[str, Any] = config["profiles"][profile]

        if "endpoint" in self._profile:
            if not isinstance(self._profile["endpoint"], str):
                raise ConfigError(
                    "Endpoint should be a string, got "
                    f"{type(self._profile['endpoint'])}."
                )
            self._endpoint = self._profile["endpoint"]

    def get_credentials(
        self,
        channel: ChannelBase,
        writer: TextIO | None = None,
        no_browser_open: bool = False,
        ssl_ctx: SSLContext | None = None,
    ) -> Credentials:
        if self._priority_bearer is not None:
            return self._priority_bearer
        if "token-file" in self._profile:
            from nebius.aio.token.file import Bearer as FileBearer

            if not isinstance(self._profile["token-file"], str):
                raise ConfigError(
                    "Token file should be a string, got "
                    f" {type(self._profile['token-file'])}."
                )
            return FileBearer(self._profile["token-file"])
        if "auth-type" not in self._profile:
            raise ConfigError("Missing auth-type in the profile.")
        auth_type = self._profile["auth-type"]
        if auth_type == "federation":
            if "federation-endpoint" not in self._profile:
                raise ConfigError("Missing federation-endpoint in the profile.")
            if not isinstance(self._profile["federation-endpoint"], str):
                raise ConfigError(
                    "Federation endpoint should be a string, got "
                    f"{type(self._profile['federation-endpoint'])}."
                )
            if "federation-id" not in self._profile:
                raise ConfigError("Missing federation-id in the profile.")
            if not isinstance(self._profile["federation-id"], str):
                raise ConfigError(
                    "Federation id should be a string, got "
                    f"{type(self._profile['federation-id'])}."
                )
            from nebius.aio.token.federation_account import FederationBearer

            if not self._client_id:
                raise ConfigError(
                    "Client ID is required for federation authentication."
                )

            log.debug(
                f"Creating FederationBearer with profile {self._profile_name}, "
                f"client_id {self._client_id}, "
                f"federation_url {self._profile['federation-endpoint']}, "
                f"federation_id {self._profile['federation-id']}, "
                f"writer {writer}, no_browser_open {no_browser_open}."
            )
            return FederationBearer(
                profile_name=self._profile_name,  # type: ignore
                client_id=self._client_id,
                federation_endpoint=self._profile["federation-endpoint"],
                federation_id=self._profile["federation-id"],
                writer=writer,
                no_browser_open=no_browser_open,
                ssl_ctx=ssl_ctx,
            )
        elif auth_type == "service account":
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

            if "service-account-id" not in self._profile:
                raise ConfigError("Missing service-account-id in the profile.")
            if not isinstance(self._profile["service-account-id"], str):
                raise ConfigError(
                    "Service account should be a string, got "
                    f"{type(self._profile['service-account-id'])}."
                )
            sa_id = self._profile["service-account-id"]
            if "public-key-id" not in self._profile:
                raise ConfigError("Missing public-key-id in the profile.")
            if not isinstance(self._profile["public-key-id"], str):
                raise ConfigError(
                    "Public key should be a string, got "
                    f"{type(self._profile['public-key-id'])}."
                )
            pk_id = self._profile["public-key-id"]
            if "private-key" not in self._profile:
                raise ConfigError("Missing private-key in the profile.")
            if not isinstance(self._profile["private-key"], str):
                raise ConfigError(
                    "Private key should be a string, got "
                    f"{type(self._profile['private-key'])}."
                )
            pk = serialization.load_pem_private_key(
                self._profile["private-key"].encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
            if not isinstance(pk, RSAPrivateKey):
                raise ConfigError(
                    f"Private key should be of type RSAPrivateKey, got {type(pk)}."
                )
            return ServiceAccountBearer(
                service_account=sa_id,
                public_key_id=pk_id,
                private_key=pk,
                channel=channel,
            )
        else:
            raise ConfigError(f"Unsupported auth-type {auth_type} in the profile.")
