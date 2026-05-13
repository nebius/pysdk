"""CLI-style configuration reader used by the SDK.

This module provides a small :class:`Config` helper to read Nebius CLI-style
configuration files and translate profile entries into credential bearers
that the SDK can use. It supports multiple auth types such as federation and
service-account credentials and will prefer an environment-supplied token if
present.

The primary entrypoint is :class:`Config.get_credentials` which returns a
credentials object ready to be consumed by :class:`nebius.aio.channel.Channel`.
"""

from contextlib import suppress
from logging import getLogger
from os import environ
from pathlib import Path
from ssl import SSLContext
from typing import Any, Literal, TextIO, cast

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
from nebius.aio.metrics import (
    METRIC_RESULT_ERROR,
    METRIC_RESULT_SUCCESS,
    AuthMetricsLike,
    MetricResult,
    MetricsLike,
    bind_auth_metrics,
    metric_duration_seconds,
    metric_start,
    record_config_metric,
)
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
    :type max_retries: `int`
    :param endpoint: Optional endpoint URL to override profile setting.
    :type endpoint: optional `str`
    :param endpoint_env: Environment variable name used to override the
        endpoint URL from the profile.
    :type endpoint_env: `str`
    :param metrics: Optional callback object or mapping that receives config
        metrics from this reader and auth metrics from credentials it creates.
        The last ``config_load`` event is replayed when metrics are attached
        later via :meth:`set_metrics`.
    :type metrics: optional object or mapping
    :param auth_metrics: Optional callback object or mapping for auth-only
        metrics emitted by credentials returned from :meth:`get_credentials`.
        Ignored when ``metrics`` is provided because full metrics are reused for
        auth callbacks.
    :type auth_metrics: optional object or mapping

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
        metrics: MetricsLike = None,
        auth_metrics: AuthMetricsLike = None,
    ) -> None:
        """Initialize the config reader, and read the config file, selecting
        the active profile.

        ``metrics`` receives both configuration metrics and auth metrics for
        credentials created by this reader. ``auth_metrics`` receives only auth
        metrics and is used only when ``metrics`` is not provided.
        """
        self._metrics = metrics
        self._auth_metrics = metrics if metrics is not None else auth_metrics
        self._last_config_load_metric: tuple[str, MetricResult, float] | None = None
        self._client_id = client_id
        self._priority_bearer: EnvBearer | None = None
        self._profile_name = profile
        self._endpoint: str | None = endpoint
        if not no_env:
            with suppress(NoTokenInEnvError):
                self._priority_bearer = EnvBearer(env_var_name=token_env)
            if self._profile_name is None:
                self._profile_name = environ.get(profile_env)
            if self._endpoint is None:
                self._endpoint = environ.get(endpoint_env)
        self._no_parent_id = no_parent_id
        self._config_file = Path(config_file).expanduser()
        self._max_retries = max_retries
        self._get_profile()

    def set_metrics(self, metrics: MetricsLike) -> None:
        """Attach full config/auth metrics and replay the last config load.

        The same callback object is propagated to credentials returned later so
        token acquisition, refresh, and cache events share the same sink.
        """

        previous = self._metrics
        self._metrics = metrics
        self._auth_metrics = metrics
        if metrics is None or metrics is previous:
            return
        if self._last_config_load_metric is not None:
            source, result, duration_seconds = self._last_config_load_metric
            record_config_metric(
                self._metrics,
                "config_load",
                source,
                result,
                duration_seconds,
            )

    def set_auth_metrics(self, metrics: AuthMetricsLike) -> None:
        """Attach auth-only metrics used by credentials returned later.

        This does not emit or replay config-reader metrics. Use
        :meth:`set_metrics` when the same sink should receive both config and
        auth events.
        """

        self._auth_metrics = metrics

    def profile_name(self) -> str | None:
        """Return the selected profile name."""

        return self._profile_name

    def _record_metric(
        self,
        kind: Literal["config_load", "credentials_resolve"],
        source: str,
        result: MetricResult,
        duration_seconds: float,
    ) -> None:
        if kind == "config_load":
            self._last_config_load_metric = (source, result, duration_seconds)
        record_config_metric(self._metrics, kind, source, result, duration_seconds)

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
                f"Parent id should be a string, got {type(self._profile['parent-id'])}."
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

        start = metric_start()
        try:
            if not self._config_file.is_file():
                raise FileNotFoundError(f"Config file {self._config_file} not found.")

            with self._config_file.open() as f:
                config = yaml.safe_load(f)

            if not isinstance(config, dict):
                raise ConfigError(f"Config should be a dictionary, got {type(config)}.")
            if "profiles" not in config:
                raise ConfigError("No profiles found in the config file.")
            if not isinstance(config["profiles"], dict):
                raise ConfigError(
                    f"Profiles should be a dictionary, got {type(config['profiles'])}."
                )
            if not config["profiles"]:
                raise ConfigError(
                    "No profiles found in the config file, setup the nebius CLI profile"
                    " first."
                )
            if self._profile_name is None:
                if "default" not in config:
                    if len(config["profiles"]) == 1:
                        self._profile_name = next(iter(config["profiles"]))
                    else:
                        raise ConfigError(
                            "No default profile found in the config file."
                        )
                else:
                    self._profile_name = config["default"]
                if self._profile_name is None:
                    raise ConfigError(
                        "No profile selected. Either set the profile in the "
                        "config setup,"
                        " set the env var NEBIUS_PROFILE or "
                        "execute `nebius profile activate`."
                    )
            profile = self._profile_name
            if not isinstance(profile, str):
                raise ConfigError(
                    f"Profile name should be a string, got {type(profile)}."
                )
            if profile not in config["profiles"]:
                raise ConfigError(f"Profile {profile} not found in the config file.")
            if not isinstance(config["profiles"][profile], dict):
                raise ConfigError(
                    f"Profile {profile} should be a dictionary, got "
                    f"{type(config['profiles'][profile])}."
                )
            self._profile: dict[str, Any] = config["profiles"][profile]

            if (
                self._endpoint is None or self._endpoint.strip() == ""
            ) and "endpoint" in self._profile:
                if not isinstance(self._profile["endpoint"], str):
                    raise ConfigError(
                        "Endpoint should be a string, got "
                        f"{type(self._profile['endpoint'])}."
                    )
                self._endpoint = self._profile["endpoint"]
        except Exception:
            self._record_metric(
                "config_load",
                "file",
                METRIC_RESULT_ERROR,
                metric_duration_seconds(start),
            )
            raise
        self._record_metric(
            "config_load",
            "file",
            METRIC_RESULT_SUCCESS,
            metric_duration_seconds(start),
        )

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

        def finish(source: str, start: float, credentials: Credentials) -> Credentials:
            self._record_metric(
                "credentials_resolve",
                source,
                METRIC_RESULT_SUCCESS,
                metric_duration_seconds(start),
            )
            return credentials

        def fail(source: str, start: float) -> None:
            self._record_metric(
                "credentials_resolve",
                source,
                METRIC_RESULT_ERROR,
                metric_duration_seconds(start),
            )

        if self._priority_bearer is not None:
            start = metric_start()
            return finish(
                "env",
                start,
                cast(
                    Credentials,
                    bind_auth_metrics(self._priority_bearer, self._auth_metrics),
                ),
            )
        if "token-file" in self._profile:
            start = metric_start()
            from nebius.aio.token.file import Bearer as FileBearer

            try:
                if not isinstance(self._profile["token-file"], str):
                    raise ConfigError(
                        "Token file should be a string, got "
                        f" {type(self._profile['token-file'])}."
                    )
                return finish(
                    "token-file",
                    start,
                    FileBearer(self._profile["token-file"], metrics=self._auth_metrics),
                )
            except Exception:
                fail("token-file", start)
                raise
        if "auth-type" not in self._profile:
            start = metric_start()
            fail("config-reader", start)
            raise ConfigError("Missing auth-type in the profile.")
        auth_type = self._profile["auth-type"]
        if auth_type == "federation":
            start = metric_start()
            try:
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

                return finish(
                    "federation",
                    start,
                    FederationBearer(
                        profile_name=self._profile_name,  # type: ignore
                        client_id=self._client_id,
                        federation_endpoint=self._profile["federation-endpoint"],
                        federation_id=self._profile["federation-id"],
                        writer=writer,
                        no_browser_open=no_browser_open,
                        ssl_ctx=ssl_ctx,
                        metrics=self._auth_metrics,
                    ),
                )
            except Exception:
                fail("federation", start)
                raise
        elif auth_type == "service account":
            start = metric_start()
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

            try:
                svc_id: str | None = None
                if "service-account-id" in self._profile:
                    if not isinstance(self._profile["service-account-id"], str):
                        raise ConfigError(
                            "Service account should be a string, got "
                            f"{type(self._profile['service-account-id'])}."
                        )
                    svc_id = self._profile["service-account-id"]

                if (
                    svc_id is not None
                    and "federated-subject-credentials-file-path" in self._profile
                ):
                    if not isinstance(
                        self._profile["federated-subject-credentials-file-path"],
                        str,
                    ):
                        raise ConfigError(
                            "federated-subject-credentials-file-path should be "
                            "a string"
                        )
                    from nebius.aio.token.federated_credentials import (
                        FederatedCredentialsBearer,
                    )

                    return finish(
                        "service-account",
                        start,
                        FederatedCredentialsBearer(
                            self._profile["federated-subject-credentials-file-path"],
                            service_account_id=svc_id,
                            channel=channel,
                            metrics=self._auth_metrics,
                        ),
                    )

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

                    return finish(
                        "service-account",
                        start,
                        ServiceAccountBearer(
                            service_account=CredentialsFileReader(
                                self._profile["service-account-credentials-file-path"]
                            ),
                            channel=channel,
                            metrics=self._auth_metrics,
                        ),
                    )

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
                            "Private key should be of type RSAPrivateKey, got "
                            f"{type(pk)}."
                        )
                    return finish(
                        "service-account",
                        start,
                        ServiceAccountBearer(
                            service_account=svc_id,
                            public_key_id=pk_id,
                            private_key=pk,
                            channel=channel,
                            metrics=self._auth_metrics,
                        ),
                    )

                if "private-key-file-path" in self._profile:
                    if not isinstance(self._profile["private-key-file-path"], str):
                        raise ConfigError("private-key-file-path should be a string")
                    from nebius.base.service_account.pk_file import (
                        Reader as PKFileReader,
                    )

                    return finish(
                        "service-account",
                        start,
                        ServiceAccountBearer(
                            service_account=PKFileReader(
                                self._profile["private-key-file-path"], pk_id, svc_id
                            ),
                            channel=channel,
                            metrics=self._auth_metrics,
                        ),
                    )

                raise ConfigError(
                    "Incomplete service account configuration: provide either "
                    "(service-account-id and federated-subject-credentials-file-path) "
                    "OR (service-account-credentials-file-path) OR "
                    "(service-account-id, public-key-id and one of "
                    "private-key / private-key-file-path)"
                )
            except Exception:
                fail("service-account", start)
                raise
        else:
            start = metric_start()
            fail("config-reader", start)
            raise ConfigError(f"Unsupported auth-type {auth_type} in the profile.")
