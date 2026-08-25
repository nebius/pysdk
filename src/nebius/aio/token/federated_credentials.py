"""Exchange federated credentials for renewable access tokens.

:class:`FederatedCredentialsBearer` combines a federated-credentials reader
or requester with exchangeable and renewable bearers. It supplies short-lived
access tokens.

The class accepts one of several inputs for ``federated_credentials``:

- a
    :class:`nebius.base.service_account.federated_credentials.FederatedCredentialsBearer`
    (a reader-like object),
- a
    :class:`nebius.base.service_account.federated_credentials.FederatedCredentialsTokenRequester`
    (an object that can construct exchange requests), or
- a string path pointing to a file understood by
  :class:`nebius.base.service_account.federated_credentials.FileFederatedCredentials`.

The resulting bearer uses :class:`nebius.aio.token.exchangeable.Bearer` for
the token exchange. It uses :class:`nebius.aio.token.renewable.Bearer` for
background refresh. For file credentials, a
:class:`nebius.aio.token.token.NamedBearer` supplies a stable diagnostic name.

Example
-------
Using a file path::

    from nebius.aio.token.federated_credentials import FederatedCredentialsBearer
    bearer = FederatedCredentialsBearer(
        "/path/to/fed-credentials.json",
        service_account_id="sa-123",
    )
    token = await bearer.receiver().fetch()

Using an existing reader/token requester::

    reader = SomeReader(...)
    bearer = FederatedCredentialsBearer(reader, service_account_id="sa-123")

"""

from datetime import timedelta

from ...base.service_account.federated_credentials import FederatedCredentialsBearer as FederatedCredentialsReader
from ...base.service_account.federated_credentials import FederatedCredentialsTokenRequester, FileFederatedCredentials
from ..abc import ClientChannelInterface
from ..metrics import AuthMetricsLike, AuthMetricsRecorder, auth_metrics_recorder
from .deferred_channel import DeferredChannel
from .exchangeable import Bearer as ExchangeableBearer
from .renewable import Bearer as RenewableBearer
from .token import Bearer as ParentBearer
from .token import NamedBearer, Receiver


class FederatedCredentialsBearer(ParentBearer):
    """Bearer that exchanges federated credentials for access tokens.

    :class:`ExchangeableBearer` performs the token exchange.
    :class:`RenewableBearer` wraps it and refreshes tokens in the background.
    Use this class with credentials from a file or reader.

    For file credentials, :class:`NamedBearer` supplies a stable cache name.

    Parameters are the same as for the underlying components and are
    passed through accordingly. See the examples in the module
    docstring for common usage patterns.

    :param federated_credentials: Either a reader, a token requester
        or a string path pointing to a file containing federated
        credentials. When a string is provided it is interpreted via
        :class:`FileFederatedCredentials`.
    :param service_account_id: Required when ``federated_credentials``
        is a reader or a string; identifies the target service account for the
        exchange.
    :param channel: Optional gRPC channel used for token exchange or
        a :class:`DeferredChannel` that resolves to a channel later.
    :param max_retries: Maximum per-request retry attempts.
    :param lifetime_safe_fraction: Fraction of token lifetime before
        triggering refresh.
    :param initial_retry_timeout: Initial retry backoff.
    :param max_retry_timeout: Maximum retry backoff.
    :param retry_timeout_exponent: Exponential backoff base.
    :param refresh_request_timeout: Timeout for a single refresh
        request.
    :param metrics: Optional auth metrics callbacks. The same recorder is
        shared across exchange, renewal, and cache layers with the
        bearer metric provider label.

    Example
    -------
    Construct a bearer and use it to initialize the SDK::

        from asyncio import Future
        from nebius.sdk import SDK
        from nebius.aio.token.federated_credentials import FederatedCredentialsBearer

        # Create a future for the channel that will be resolved with the SDK
        channel_future = Future()

        sdk = SDK(
            credentials=FederatedCredentialsBearer(
                federated_credentials="/path/to/fed-credentials.json",
                service_account_id="your-service-account-id",
                channel=channel_future,
            ),
            user_agent_prefix="example-application/1.0",
        )

        # Resolve the future with the newly created SDK
        channel_future.set_result(sdk)

    """

    def __init__(
        self,
        federated_credentials: (FederatedCredentialsTokenRequester | FederatedCredentialsReader | str),
        service_account_id: str | None = None,
        channel: ClientChannelInterface | DeferredChannel | None = None,
        max_retries: int = 2,
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        refresh_request_timeout: timedelta = timedelta(seconds=5),
        metrics: AuthMetricsLike = None,
    ) -> None:
        """Create a federated credentials backed bearer."""
        if isinstance(federated_credentials, str):
            federated_credentials = FileFederatedCredentials(federated_credentials)
        if isinstance(federated_credentials, FederatedCredentialsReader):
            if not isinstance(service_account_id, str):
                raise TypeError(
                    "Service account ID must be provided as a string when federated_credentials is a string.",
                )
            federated_credentials = FederatedCredentialsTokenRequester(
                service_account_id=service_account_id,
                credentials=federated_credentials,
            )

        if not isinstance(federated_credentials, FederatedCredentialsTokenRequester):  # type: ignore[unused-ignore]
            raise TypeError(
                "federated_credentials must be FederatedCredentialsTokenRequester, "
                "FederatedCredentialsBearer or string"
                f", got {type(federated_credentials)}",
            )

        self._metrics: AuthMetricsRecorder = auth_metrics_recorder(metrics, "federated-credentials")

        self._exchangeable = ExchangeableBearer(
            federated_credentials,
            channel=channel,
            max_retries=max_retries,
            metrics=self._metrics,
        )
        self._source: ParentBearer = RenewableBearer(
            self._exchangeable,
            max_retries=max_retries,
            lifetime_safe_fraction=lifetime_safe_fraction,
            initial_retry_timeout=initial_retry_timeout,
            max_retry_timeout=max_retry_timeout,
            retry_timeout_exponent=retry_timeout_exponent,
            refresh_request_timeout=refresh_request_timeout,
            metrics=self._metrics,
            provider=self._metrics.provider,
        )

        if isinstance(federated_credentials.credentials, FileFederatedCredentials):
            self._source = NamedBearer(
                self._source,
                f"federated-credentials/{federated_credentials.service_account_id}"
                f"/{federated_credentials.credentials.file_path}",
            )

    def set_channel(self, channel: ClientChannelInterface) -> None:
        """Attach a concrete gRPC channel to the underlying exchangeable.

        This method gives the channel to the embedded
        :class:`ExchangeableBearer`.
        """
        self._exchangeable.set_channel(channel)

    @property
    def wrapped(self) -> "ParentBearer|None":
        """Return the outermost wrapped bearer (typically the renewable source).

        :returns: The wrapped :class:`ParentBearer`.
        """
        return self._source

    def receiver(self) -> "Receiver":
        """Return a receiver constructed from the underlying renewable bearer.

        :returns: A :class:`Receiver` from the underlying renewable bearer.
        """
        return self._source.receiver()

    def set_metrics(self, metrics: AuthMetricsLike) -> None:
        """Attach auth metrics callbacks and propagate them to inner bearers."""
        self._metrics.set_metrics(metrics)
        self._exchangeable.set_metrics(self._metrics)
        setter = getattr(self._source, "set_metrics", None)
        if callable(setter):
            setter(self._metrics)
