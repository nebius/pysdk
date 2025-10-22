"""CLI-style configuration reader used by the SDK.

This module provides a small :class:`Config` helper to read Nebius CLI-style
configuration files and translate profile entries into credential bearers
that the SDK can use. It supports multiple auth types such as federation and
service-account credentials and will prefer an environment-supplied token if
present.

The primary entrypoint is :class:`Config.get_credentials` which returns a
credentials object ready to be consumed by :class:`nebius.aio.channel.Channel`.
"""

from logging import getLogger
from os import environ
from os.path import isfile
from pathlib import Path
from ssl import SSLContext
from typing import Any, TextIO

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
from nebius.aio.token.service_account import ServiceAccountBearer
from nebius.aio.token.static import EnvBearer, NoTokenInEnvError
from nebius.aio.token.token import Bearer as TokenBearer
from nebius.aio.token.token import Token
from nebius.base.constants import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    ENDPOINT_ENV,
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
    """Base exception for configuration-related errors."""


class NoParentIdError(ConfigError):
    """Raised when a requested parent id is missing or explicitly disabled."""


class Config:
    """Reader for Nebius CLI-style configuration files.

    The :class:`Config` class locates and parses a YAML-based configuration
    file (by default under ``~/.nebius/config.yaml``) and exposes convenience
    methods to obtain the default parent id, endpoint, and credentials
    configured for the active profile.

    :param client_id: Optional client id used for federation flows.
    :type client_id: optional `str`
    :param config_file: Path to the configuration YAML file.
    :type config_file: `str` | `Path`
    :param profile: Optional profile name to select; when omitted the
        default profile from the config or the environment variable
        indicated by ``profile_env`` is used.
    :type profile: optional `str`
    :param profile_env: Environment variable name used to select a profile.
    :type profile_env: `str`
    :param token_env: Environment variable name that may contain an IAM token
        and will take priority over file-based credentials.
    :type token_env: `str`
    :param no_env: If True skip environment token lookup, profile selection, and
        endpoint override. If you want to disable only one of these features, you can
        set the env variable name to some invalid value.
    :type no_env: `bool`
    :param no_parent_id: If True disable automatic parent id resolution.
    :type no_parent_id: `bool`
    :param max_retries: Maximum number of auth retries when interacting with
        external services (passed to underlying bearers).
    :param endpoint: Optional endpoint URL to override profile setting.
    :type endpoint: optional `str`
    :param endpoint_env: Environment variable name used to override the
        endpoint URL from the profile.
    :type endpoint_env: `str`
    :type max_retries: `int`

    Example
    -------

    Initialize the SDK with CLI config::

        from nebius.sdk import SDK
        from nebius.aio.cli_config import Config

        # Initialize SDK with CLI config reader
        sdk = SDK(config_reader=Config())

        # The config reader will automatically handle authentication
        # based on the active CLI profile

        # You can also access config properties directly
        config = Config()
        print(f"Default parent ID: {config.parent_id}")
        print(f"Endpoint: {config.endpoint()}")
    """

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
        endpoint: str | None = None,
        endpoint_env: str = ENDPOINT_ENV,
    ) -> None:
        """Initialize the config reader, and read the config file, selecting
        the active profile.
        """
        self._client_id = client_id
        self._priority_bearer: EnvBearer | None = None
        self._profile_name = profile
        self._endpoint: str | None = endpoint
        if not no_env:
            try:
                self._priority_bearer = EnvBearer(env_var_name=token_env)
            except NoTokenInEnvError:
                pass
            if self._profile_name is None:
                self._profile_name = environ.get(profile_env, None)
            if self._endpoint is None:
                self._endpoint = environ.get(endpoint_env, None)
        self._no_parent_id = no_parent_id
        self._config_file = Path(config_file).expanduser()
        self._max_retries = max_retries
        self._get_profile()

    @property
    def parent_id(self) -> str:
        """Return the parent id from the active profile.

        The value is read from the active profile's ``parent-id`` field and
        validated to be a non-empty string.

        :returns: the parent id configured for the active profile
        :rtype: `str`
        :raises NoParentIdError: if parent id usage is disabled or the value is
            missing or empty in the profile
        :raises ConfigError: if the profile contains a non-string parent-id
        """
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
        """Return the configured endpoint for the active profile.

        If the profile does not define an endpoint this method returns an
        empty string.

        :returns: endpoint string or empty string when not configured
        :rtype: `str`
        """
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

        if (
            self._endpoint is None
            or self._endpoint == ""
            and "endpoint" in self._profile
        ):
            if not isinstance(self._profile["endpoint"], str):
                raise ConfigError(
                    "Endpoint should be a string, got "
                    f"{type(self._profile['endpoint'])}."
                )
            self._endpoint = self._profile["endpoint"]

    def get_credentials(
        self,
        channel: ClientChannelInterface,
        writer: TextIO | None = None,
        no_browser_open: bool = False,
        ssl_ctx: SSLContext | None = None,
    ) -> Credentials:
        """Resolve and return credentials for the active profile.

        This method consults, in order of priority:

        1. An environment-provided token bearer (if present and enabled).
        2. A token file specified by ``token-file`` in the profile.
        3. The profile's ``auth-type`` which may be ``federation`` or
           ``service account`` and will create the corresponding bearer
           implementation.

        The returned object is suitable to be consumed by
        :class:`nebius.aio.channel.Channel` and may be one of
        :class:`nebius.aio.authorization.authorization.Provider`, a
        :class:`nebius.aio.token.token.Bearer`, a :class:`TokenRequester`
        reader, a low-level :class:`nebius.aio.token.token.Token`, or a raw
        string token depending on the profile and environment.

        :param channel: channel instance used for network-bound credential flows
        :type channel: :class:`ClientChannelInterface`
        :param writer: optional text stream used by interactive flows (federation)
        :type writer: optional `TextIO`
        :param no_browser_open: when True, federation flows will not open browsers
        :type no_browser_open: `bool`
        :param ssl_ctx: optional SSLContext forwarded to federation flows
        :type ssl_ctx: optional `SSLContext`

        :returns: a credentials object appropriate for the active profile
        :rtype: :class:`Provider`, :class:`nebius.aio.token.token.Bearer`,
            :class:`TokenRequester`, :class:`Token` or `str`
        :raises ConfigError: for malformed or missing profile entries
        """
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

            # Federation bearer already wraps underlying signer with a file-cache
            # renewable bearer. Return it directly.
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

            # Possible sources (priority):
            # 1) federated-subject-credentials-file-path + service-account-id
            # 2) service-account-credentials-file-path
            # 3) inline private-key with service-account-id + public-key-id
            # 4) private-key-file-path with service-account-id + public-key-id

            svc_id: str | None = None
            if "service-account-id" in self._profile:
                if not isinstance(self._profile["service-account-id"], str):
                    raise ConfigError(
                        "Service account should be a string, got "
                        f"{type(self._profile['service-account-id'])}."
                    )
                svc_id = self._profile["service-account-id"]

            # 1) federated subject credentials file
            if (
                svc_id is not None
                and "federated-subject-credentials-file-path" in self._profile
            ):
                if not isinstance(
                    self._profile["federated-subject-credentials-file-path"], str
                ):
                    raise ConfigError(
                        "federated-subject-credentials-file-path should be a string"
                    )
                # Use the federated credentials bearer (file-backed) to supply
                # the actor token for token-exchange. Do not treat this as a
                # service-account credentials file.
                from nebius.aio.token.federated_credentials import (
                    FederatedCredentialsBearer,
                )

                return FederatedCredentialsBearer(
                    self._profile["federated-subject-credentials-file-path"],
                    service_account_id=svc_id,
                    channel=channel,
                )

            # 2) service account credentials file
            if "service-account-credentials-file-path" in self._profile:
                if not isinstance(
                    self._profile["service-account-credentials-file-path"], str
                ):
                    raise ConfigError(
                        "service-account-credentials-file-path should be a string"
                    )
                from nebius.base.service_account.credentials_file import (
                    Reader as CredentialsFileReader,
                )

                return ServiceAccountBearer(
                    service_account=CredentialsFileReader(
                        self._profile["service-account-credentials-file-path"]
                    ),
                    channel=channel,
                )

            # 3 & 4) inline private-key or private-key file path
            if svc_id is None:
                raise ConfigError("Missing service-account-id in the profile.")

            if "public-key-id" not in self._profile:
                raise ConfigError("Missing public-key-id in the profile.")
            if not isinstance(self._profile["public-key-id"], str):
                raise ConfigError(
                    "Public key should be a string, got "
                    f"{type(self._profile['public-key-id'])}."
                )
            pk_id = self._profile["public-key-id"]

            # inline private-key
            if "private-key" in self._profile:
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
                    service_account=svc_id,
                    public_key_id=pk_id,
                    private_key=pk,
                    channel=channel,
                )

            # private-key file path
            if "private-key-file-path" in self._profile:
                if not isinstance(self._profile["private-key-file-path"], str):
                    raise ConfigError("private-key-file-path should be a string")
                from nebius.base.service_account.pk_file import Reader as PKFileReader

                return ServiceAccountBearer(
                    service_account=PKFileReader(
                        self._profile["private-key-file-path"], pk_id, svc_id
                    ),
                    channel=channel,
                )

            # Nothing matched
            raise ConfigError(
                "Incomplete service account configuration: provide either "
                "(service-account-id and federated-subject-credentials-file-path) OR "
                "(service-account-credentials-file-path) OR "
                "(service-account-id, public-key-id and one of "
                "private-key / private-key-file-path)"
            )
        else:
            raise ConfigError(f"Unsupported auth-type {auth_type} in the profile.")
