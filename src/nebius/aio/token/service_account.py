"""Service-account based bearer for asynchronous authentication.

- This module provides a convenience :class:`ServiceAccountBearer` which
- composes several internal bearer implementations to support exchanging
- service account credentials for access tokens, automatic renewal and a
- stable diagnostic name.

- The bearer may be constructed from one of three inputs:
    - a :class:`nebius.base.service_account.service_account.Reader` instance
        which will be used to read the actual
        :class:`nebius.base.service_account.service_account.ServiceAccount`;
- a ready-made :class:`nebius.base.service_account.service_account.ServiceAccount`;
- a string service account id together with ``private_key`` and ``public_key_id``
  which will be used to build an in-memory :class:`ServiceAccount`.

Examples
Constructing from an environment/CLI-backed reader (recommended):

>>> from nebius.aio.token.service_account import ServiceAccountBearer
>>> from nebius.base.service_account.pk_file import Reader as PKReader
>>> bearer = ServiceAccountBearer(PKReader("/path/to/private_key.pem"))

Constructing from explicit values (private key object required):

>>> from cryptography.hazmat.primitives.serialization import load_pem_private_key
>>> from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
>>> with open("/path/to/private_key.pem","rb") as fh:
...     key = load_pem_private_key(fh.read(), password=None)
>>> bearer = ServiceAccountBearer(
...     "service-account-id",
...     private_key=key,  # type: RSAPrivateKey
...     public_key_id="public-key-id",
... )

The resulting bearer exposes the :meth:`receiver` method used by the SDK's
authentication layer. See :mod:`nebius.aio.token.token` for the receiver and
token abstractions.
"""

from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.token.deferred_channel import DeferredChannel
from nebius.aio.token.exchangeable import Bearer as ExchangeableBearer
from nebius.aio.token.renewable import Bearer as RenewableBearer
from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import NamedBearer, Receiver
from nebius.base.service_account.service_account import (
    Reader as ServiceAccountReader,
)
from nebius.base.service_account.service_account import (
    ServiceAccount,
)
from nebius.base.service_account.static import Reader as ServiceAccountReaderStatic


class ServiceAccountBearer(ParentBearer):
    """Bearer that obtains tokens using a service account.

    The class composes an exchangeable bearer (that performs the token
    exchange), wraps it into a renewable bearer (to handle background token
    refresh) and finally assigns a stable ``name`` using :class:`NamedBearer`.

    The chain from the outermost to innermost is as follows:

      * :class:`NamedBearer` ->
      * :class:`RenewableBearer` ->
      * :class:`ExchangeableBearer` ->
      * :class:`ServiceAccountReader` ->
      * :class:`ServiceAccount`

    :param service_account: Service account credentials used to obtain tokens.
        May be a :class:`ServiceAccountReader`, a :class:`ServiceAccount` or a
        string service account id.
    :param channel: A channel used to perform the token exchange. This channel must
        be provided before any token fetch operation, or a :class:`DeferredChannel`
        may be used to set the channel asynchronously. If neither is provided,
        token fetch operations will fail until :meth:`set_channel` is called.
    :param private_key: When ``service_account`` is a string id, this private key
        is used to sign token exchange requests. Must not be provided if the service
        account is provided as a :class:`ServiceAccount` or
        :class:`ServiceAccountReader`.
    :param public_key_id: When ``service_account`` is a string id, this is the
        public key ID corresponding to the private key. Must not be provided if the
        service account is provided as a :class:`ServiceAccount` or
        :class:`ServiceAccountReader`.
    :param max_retries: Maximum number of retries for token fetch operations.
    :param lifetime_safe_fraction: Fraction of token lifetime considered safe
        to use before triggering a refresh.
    :param initial_retry_timeout: Initial delay between retry attempts for
        refresh operations.
    :param max_retry_timeout: Maximum delay between retry attempts for
        refresh operations.
    :param retry_timeout_exponent: Exponential backoff exponent for retry
        delays.
    :param refresh_request_timeout: Timeout for individual token refresh
        requests.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from asyncio import Future
        from nebius.sdk import SDK
        from nebius.aio.token.service_account import ServiceAccountBearer
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        with open("/path/to/private_key.pem", "rb") as fh:
            private_key = load_pem_private_key(fh.read(), password=None)

        # Create a future for the channel that will be resolved with the SDK
        channel_future = Future()

        sdk = SDK(credentials=ServiceAccountBearer(
            "service-account-id",
            private_key=private_key,
            public_key_id="public-key-id",
            channel=channel_future,
        ))

        # Resolve the future with the newly created SDK
        channel_future.set_result(sdk)
    """

    def __init__(
        self,
        service_account: ServiceAccountReader | ServiceAccount | str,
        channel: ClientChannelInterface | DeferredChannel | None = None,
        private_key: RSAPrivateKey | None = None,
        public_key_id: str | None = None,
        max_retries: int = 2,
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        refresh_request_timeout: timedelta = timedelta(seconds=5),
    ) -> None:
        """Initialize a service-account based bearer.

        This is essentially a convenience wrapper that composes several
        internal bearer implementations to provide a ready-to-use bearer
        that fetches tokens using service account credentials and is being conveniently
        named with the service account parameters.

        **Important note:**
        When constructing the bearer using a dynamic :class:`ServiceAccountReader`,
        the name of the bearer will reflect the service account as read during
        construction time. If the reader returns different service accounts
        on subsequent reads, the name will not reflect those changes.
        """
        reader: ServiceAccountReader | None = None
        if isinstance(service_account, ServiceAccountReader):
            reader = service_account
            service_account = service_account.read()
        if isinstance(service_account, str):
            if not isinstance(private_key, RSAPrivateKey):
                raise TypeError(
                    "Private key must be provided as RSAPrivateKey instance "
                    "when service_account is a string."
                )
            if not isinstance(public_key_id, str):
                raise TypeError(
                    "Public key ID must be provided as a string when service_account "
                    "is a string."
                )
            service_account = ServiceAccount(
                private_key=private_key,
                public_key_id=public_key_id,
                service_account_id=service_account,
            )
        else:
            if private_key is not None or public_key_id is not None:
                raise ValueError(
                    "Private key and public key ID must not be provided "
                    "when service_account is a ServiceAccount or ServiceAccountReader "
                    "instance."
                )
        if not isinstance(service_account, ServiceAccount):  # type: ignore[unused-ignore]
            raise TypeError(
                "service_account must be ServiceAccountReader, ServiceAccount or string"
                f", got {type(service_account)}"
            )
        if reader is None:
            reader = ServiceAccountReaderStatic(service_account)
        sa_id = service_account.service_account_id
        public_key_id = service_account.public_key_id
        private_key = service_account.private_key

        self._exchangeable = ExchangeableBearer(
            reader,
            channel=channel,
            max_retries=max_retries,
        )

        self._source = NamedBearer(
            RenewableBearer(
                self._exchangeable,
                max_retries=max_retries,
                lifetime_safe_fraction=lifetime_safe_fraction,
                initial_retry_timeout=initial_retry_timeout,
                max_retry_timeout=max_retry_timeout,
                retry_timeout_exponent=retry_timeout_exponent,
                refresh_request_timeout=refresh_request_timeout,
            ),
            f"service-account/{sa_id}/{public_key_id}",
        )

    def set_channel(self, channel: ClientChannelInterface) -> None:
        """Attach a concrete channel to the exchangeable bearer.

        This function must be used when a channel was not available at construction
        and a :class:`DeferredChannel` was not provided.

        :param channel: The concrete channel to attach.
        :type channel: :class:`ClientChannelInterface`
        """
        self._exchangeable.set_channel(channel)

    @property
    def wrapped(self) -> "ParentBearer|None":
        """Returns the outermost underlying bearer :class:`NamedBearer`."""
        return self._source

    def receiver(self) -> "Receiver":
        """Calls the receiver of the underlying bearer :class:`NamedBearer`."""
        return self._source.receiver()
