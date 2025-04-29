from os.path import isfile
from pathlib import Path
from typing import Any

from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
from nebius.aio.token.static import EnvBearer, NoTokenInEnvError
from nebius.aio.token.token import Bearer as TokenBearer
from nebius.aio.token.token import Token
from nebius.base.constants import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
)
from nebius.base.service_account.service_account import (
    TokenRequester as ServiceAccountReader,
)

Credentials = AuthorizationProvider | TokenBearer | ServiceAccountReader | Token | str


class Config:
    def __init__(
        self,
        config_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CONFIG_FILE,
        profile: str | None = None,
        no_env: bool = False,
        max_retries: int = 2,
    ) -> None:
        self._priority_bearer: EnvBearer | None = None
        if not no_env:
            try:
                self._priority_bearer = EnvBearer()
            except NoTokenInEnvError:
                pass
        self._config_file = Path(config_file).expanduser()
        self._profile_name = profile
        self._endpoint: str | None = None
        self._max_retries = max_retries
        self._get_profile()

    def parent_id(self) -> str:
        if "parent-id" not in self._profile:
            raise ValueError("Missing parent-id in the profile.")
        if not isinstance(self._profile["parent-id"], str):
            raise ValueError(
                "Parent id should be a string, got "
                f"{type(self._profile['parent-id'])}."
            )
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
            raise ValueError("No profiles found in the config file.")
        if not isinstance(config["profiles"], dict):
            raise ValueError(
                f"Profiles should be a dictionary, got {type(config['profiles'])}."
            )
        if self._profile_name is None:
            if "default" not in config:
                raise ValueError("No default profile found in the config file.")
            self._profile_name = config["default"]
        profile = self._profile_name
        if not isinstance(profile, str):
            raise ValueError(f"Profile name should be a string, got {type(profile)}.")
        if profile not in config["profiles"]:
            raise ValueError(f"Profile {profile} not found in the config file.")
        if not isinstance(config["profiles"][profile], dict):
            raise ValueError(
                f"Profile {profile} should be a dictionary, got "
                f"{type(config['profiles'][profile])}."
            )
        self._profile: dict[str, Any] = config["profiles"][profile]

        if "endpoint" in self._profile:
            if not isinstance(self._profile["endpoint"], str):
                raise ValueError(
                    "Endpoint should be a string, got "
                    f"{type(self._profile['endpoint'])}."
                )
            self._endpoint = self._profile["endpoint"]

    def get_credentials(
        self,
    ) -> Credentials:
        if self._priority_bearer is not None:
            return self._priority_bearer
        if "token-file" in self._profile:
            from nebius.aio.token.file import Bearer as FileBearer

            if not isinstance(self._profile["token-file"], str):
                raise ValueError(
                    "Token file should be a string, got "
                    f" {type(self._profile['token-file'])}."
                )
            return FileBearer(self._profile["token-file"])
        if "auth-type" not in self._profile:
            raise ValueError("Missing auth-type in the profile.")
        auth_type = self._profile["auth-type"]
        if auth_type == "federation":
            raise NotImplementedError(
                "Federation authentication is not implemented yet."
            )
        elif auth_type == "service account":
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

            from nebius.base.service_account.service_account import ServiceAccount
            from nebius.base.service_account.static import (
                Reader as ServiceAccountReaderStatic,
            )

            if "service-account-id" not in self._profile:
                raise ValueError("Missing service-account-id in the profile.")
            if not isinstance(self._profile["service-account-id"], str):
                raise ValueError(
                    "Service account should be a string, got "
                    f"{type(self._profile['service-account-id'])}."
                )
            sa_id = self._profile["service-account-id"]
            if "public-key-id" not in self._profile:
                raise ValueError("Missing public-key-id in the profile.")
            if not isinstance(self._profile["public-key-id"], str):
                raise ValueError(
                    "Public key should be a string, got "
                    f"{type(self._profile['public-key-id'])}."
                )
            pk_id = self._profile["public-key-id"]
            if "private-key" not in self._profile:
                raise ValueError("Missing private-key in the profile.")
            if not isinstance(self._profile["private-key"], str):
                raise ValueError(
                    "Private key should be a string, got "
                    f"{type(self._profile['private-key'])}."
                )
            pk = serialization.load_pem_private_key(
                self._profile["private-key"].encode("utf-8"),
                password=None,
                backend=default_backend(),
            )
            if not isinstance(pk, RSAPrivateKey):
                raise ValueError(
                    f"Private key should be of type RSAPrivateKey, got {type(pk)}."
                )
            return ServiceAccountReaderStatic(
                service_account=ServiceAccount(
                    private_key=pk,
                    public_key_id=pk_id,
                    service_account_id=sa_id,
                )
            )
        else:
            raise ValueError(f"Unsupported auth-type {auth_type} in the profile.")
