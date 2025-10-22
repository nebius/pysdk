"""Convenience bearer for federated credentials.

This module exposes :class:`FederatedCredentialsBearer`, a convenience
wrapper that composes the low-level federated credentials reader/token
requester implementations with the exchangeable and renewable bearers
to provide a ready-to-use bearer producing short-lived access tokens.

The class accepts one of several inputs for ``federated_credentials``:

- a
    :class:`nebius.base.service_account.federated_credentials.FederatedCredentialsBearer`
    (a reader-like object),
- a
    :class:`nebius.base.service_account.federated_credentials.FederatedCredentialsTokenRequester`
    (an object that can construct exchange requests), or
- a string path pointing to a file understood by
  :class:`nebius.base.service_account.federated_credentials.FileFederatedCredentials`.

The resulting bearer performs the token exchange via
:class:`nebius.aio.token.exchangeable.Bearer` and adds background
refresh via :class:`nebius.aio.token.renewable.Bearer`. When the
underlying credentials originate from a file the resulting bearer is
wrapped in a :class:`nebius.aio.token.token.NamedBearer` to provide a
stable diagnostic name.

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

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.token.deferred_channel import DeferredChannel
from nebius.aio.token.exchangeable import Bearer as ExchangeableBearer
from nebius.aio.token.renewable import Bearer as RenewableBearer
from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import NamedBearer, Receiver
from nebius.base.service_account.federated_credentials import (
    FederatedCredentialsBearer as FederatedCredentialsReader,
)
from nebius.base.service_account.federated_credentials import (
    FederatedCredentialsTokenRequester,
    FileFederatedCredentials,
)


class FederatedCredentialsBearer(ParentBearer):
    """Bearer that exchanges federated credentials for access tokens.

    The class composes an :class:`ExchangeableBearer` (performs the
    token exchange) wrapped by :class:`RenewableBearer` (background
    refresh). It is a convenience wrapper for the common case where a
    consumer has federated credentials stored in a file or provided via
    a reader.

    If the federated credentials originate from a file, the resulting
    bearer is wrapped in a :class:`NamedBearer` to provide a stable cacheable name.

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

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from asyncio import Future
        from nebius.sdk import SDK
        from nebius.aio.token.federated_credentials import FederatedCredentialsBearer

        # Create a future for the channel that will be resolved with the SDK
        channel_future = Future()

        sdk = SDK(credentials=FederatedCredentialsBearer(
            federated_credentials="/path/to/fed-credentials.json",
            service_account_id="your-service-account-id",
            channel=channel_future,
        ))

        # Resolve the future with the newly created SDK
        channel_future.set_result(sdk)
    """

    def __init__(
        self,
        federated_credentials: (
            FederatedCredentialsTokenRequester | FederatedCredentialsReader | str
        ),
        service_account_id: str | None = None,
        channel: ClientChannelInterface | DeferredChannel | None = None,
        max_retries: int = 2,
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        refresh_request_timeout: timedelta = timedelta(seconds=5),
    ) -> None:
        """Create a federated credentials backed bearer."""
        if isinstance(federated_credentials, str):
            federated_credentials = FileFederatedCredentials(federated_credentials)
        if isinstance(federated_credentials, FederatedCredentialsReader):
            if not isinstance(service_account_id, str):
                raise TypeError(
                    "Service account ID must be provided as a string when "
                    "federated_credentials is a string."
                )
            federated_credentials = FederatedCredentialsTokenRequester(
                service_account_id=service_account_id,
                credentials=federated_credentials,
            )

        if not isinstance(federated_credentials, FederatedCredentialsTokenRequester):  # type: ignore[unused-ignore]
            raise TypeError(
                "federated_credentials must be FederatedCredentialsTokenRequester, "
                "FederatedCredentialsBearer or string"
                f", got {type(federated_credentials)}"
            )

        self._exchangeable = ExchangeableBearer(
            federated_credentials,
            channel=channel,
            max_retries=max_retries,
        )
        self._source: ParentBearer = RenewableBearer(
            self._exchangeable,
            max_retries=max_retries,
            lifetime_safe_fraction=lifetime_safe_fraction,
            initial_retry_timeout=initial_retry_timeout,
            max_retry_timeout=max_retry_timeout,
            retry_timeout_exponent=retry_timeout_exponent,
            refresh_request_timeout=refresh_request_timeout,
        )

        if isinstance(federated_credentials.credentials, FileFederatedCredentials):
            self._source = NamedBearer(
                self._source,
                f"federated-credentials/{federated_credentials.service_account_id}"
                f"/{federated_credentials.credentials.file_path}",
            )

    def set_channel(self, channel: ClientChannelInterface) -> None:
        """Attach a concrete gRPC channel to the underlying exchangeable.

        This is a simple convenience method that forwards the channel to
        the embedded :class:`ExchangeableBearer`.
        """
        self._exchangeable.set_channel(channel)

    @property
    def wrapped(self) -> "ParentBearer|None":
        """Return the outermost wrapped bearer (typically the renewable source).

        :returns: The wrapped :class:`ParentBearer` used by this convenience wrapper.
        """
        return self._source

    def receiver(self) -> "Receiver":
        """Return a per-request receiver constructed from the underlying renewable
        bearer.

        :returns: A :class:`Receiver` from the underlying renewable bearer.
        """
        return self._source.receiver()
