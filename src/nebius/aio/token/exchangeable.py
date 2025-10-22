"""Token exchange bearer and receiver.

This module implements a bearer that exchanges a permanent service-account JWT
or similar credentials for a short-lived access token using the
``TokenExchangeService``. The exchange is performed via a gRPC call
and the response is converted into a :class:`Token` instance.

The primary classes are:

- :class:`Receiver` -- performs the token exchange request for a single
    fetch and exposes ``can_retry`` logic.
- :class:`Bearer` -- holds the channel and requester and constructs
    per-request receivers.

Examples
--------

Create a bearer with a preconfigured channel::

    from nebius.aio.token.exchangeable import Bearer
    bearer = Bearer(requester, channel=my_channel)
    token = await bearer.receiver().fetch()

"""

from collections.abc import Awaitable, Coroutine
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

from grpc.aio import AioRpcError
from grpc_status import rpc_status

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.authorization.options import OPTION_TYPE, Types
from nebius.api.nebius.iam.v1 import CreateTokenResponse, TokenExchangeServiceClient
from nebius.base.error import SDKError
from nebius.base.metadata import Metadata as NebiusMetadata
from nebius.base.service_account.service_account import TokenRequester
from nebius.base.token_sanitizer import TokenSanitizer

from .deferred_channel import DeferredChannel
from .options import OPTION_MAX_RETRIES
from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

sanitizer = TokenSanitizer.access_token_sanitizer()

log = getLogger(__name__)


class UnsupportedResponseError(SDKError):
    """Raised when the token exchange returned an unexpected response type.

    :param expected: The expected response type name.
    :param resp: The actual response object received.
    """

    def __init__(self, expected: str, resp: Any) -> None:
        """Initialize the error."""
        super().__init__(
            f"Unsupported response received: expected {expected},"
            f" received {type(resp)}"
        )


class UnsupportedTokenTypeError(SDKError):
    """Raised when the token exchange returned a non-Bearer token."""

    def __init__(self, token_type: str) -> None:
        """Initialize the error.

        :param token_type: The token type string received from the server.
        """
        super().__init__(
            f"Unsupported token received: expected Bearer, received {token_type}"
        )


class Receiver(ParentReceiver):
    """Receiver that performs a token exchange over gRPC.

    The receiver constructs an exchange request using the provided
    :class:`nebius.base.service_account.service_account.TokenRequester`
    and calls the :class:`TokenExchangeServiceClient.exchange` RPC.

    :param requester: Object that can construct the exchange request.
    :param service: Either a ready-made
        :class:`TokenExchangeServiceClient` or an awaitable resolving to
        one (useful when the channel is created asynchronously).
    :param max_retries: Maximum retry attempts for this receiver.
    """

    def __init__(
        self,
        requester: TokenRequester,
        service: TokenExchangeServiceClient | Awaitable[TokenExchangeServiceClient],
        max_retries: int = 2,
    ) -> None:
        """Initialize the receiver."""
        super().__init__()
        self._requester = requester
        self._svc = service
        self._max_retries = max_retries

        self._trial = 0

    def _raise_request_error(self, err: AioRpcError) -> None:
        """Convert a gRPC AioRpcError into a RequestError with diagnostics.

        The function extracts request and trace ids from the initial
        metadata and converts the gRPC status into the SDK's
        :class:`nebius.aio.service_error.RequestError` type.

        :param err: The original gRPC AioRpcError.
        :raises RequestError: always raised with enriched diagnostics.
        """
        initial_metadata = NebiusMetadata(err.initial_metadata())
        request_id = initial_metadata.get_one("x-request-id", "")
        trace_id = initial_metadata.get_one("x-trace-id", "")
        status = rpc_status.from_call(err)  # type: ignore
        from nebius.aio.service_error import RequestError, RequestStatusExtended

        if status is None:
            self._status = RequestStatusExtended(
                code=err.code(),
                message=err.details(),
                details=[],
                service_errors=[],
                request_id=request_id,
                trace_id=trace_id,
            )
            raise RequestError(self._status) from None

        self._status = RequestStatusExtended.from_rpc_status(  # type: ignore[unused-ignore]
            status,
            trace_id=trace_id,
            request_id=request_id,
        )
        raise RequestError(self._status) from None

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Perform the exchange RPC and return a :class:`Token`.

        :param timeout: Optional RPC timeout in seconds forwarded to the
            underlying gRPC stub.
        :param options: Optional map of request-specific options (currently
            unused).
        :returns: A :class:`Token` representing the exchanged access token.
        :raises nebius.aio.service_error.RequestError: when the RPC returns a service
            error.
        :raises UnsupportedResponseError: when the RPC returns an unexpected
            payload type.
        :raises UnsupportedTokenTypeError: when the received token type is not
            ``"Bearer"``.
        """
        self._trial += 1
        req = self._requester.get_exchange_token_request()

        now = datetime.now(timezone.utc)

        log.debug(f"fetching new token, attempt: {self._trial}, timeout: {timeout}")

        ret = None
        try:
            if isinstance(self._svc, Awaitable):
                self._svc = await self._svc
            ret = await self._svc.exchange(
                req,
                timeout=timeout,
                auth_options={OPTION_TYPE: Types.DISABLE},
            )
        except AioRpcError as e:
            self._raise_request_error(e)
        if not isinstance(ret, CreateTokenResponse):
            raise UnsupportedResponseError(CreateTokenResponse.__name__, ret)

        if ret.token_type != "Bearer":  # noqa: S105 — not a password
            raise UnsupportedTokenTypeError(ret.token_type)

        log.debug(
            f"token fetched: {sanitizer.sanitize(ret.access_token)},"
            f" expires in: {ret.expires_in} seconds."
        )
        return Token(
            token=ret.access_token, expiration=now + timedelta(seconds=ret.expires_in)
        )

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Decide whether the receiver should attempt another retry.

        The method honours the per-request :data:`OPTION_MAX_RETRIES` override
        if present and parses it as an integer. Invalid values are logged
        and ignored.
        """
        max_retries = self._max_retries
        if options is not None and OPTION_MAX_RETRIES in options:
            value = options[OPTION_MAX_RETRIES]
            try:
                max_retries = int(value)
            except ValueError as err:
                log.error(f"option {OPTION_MAX_RETRIES} is not valid integer: {err=}")
        if self._trial >= max_retries:
            log.debug("token max retries reached, cannot retry")
            return False
        return True


class Bearer(ParentBearer):
    """Bearer that creates receivers performing token exchange.

    The bearer accepts either a concrete gRPC channel or an awaitable
    resolving to one. The channel is wrapped in a
    :class:`TokenExchangeServiceClient` and used by receivers to perform
    the exchange RPC.

    :param requester: Object that knows how to build an exchange
        request for the current service account.
    :param channel: gRPC channel or awaitable resolving to one. If
        omitted, callers must call :meth:`set_channel` before
        obtaining a receiver.
    :param max_retries: Default retry attempts for receivers created
        by this bearer.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from asyncio import Future
        from nebius.sdk import SDK
        from nebius.aio.token.exchangeable import Bearer
        from nebius.base.service_account.pk_file import Reader as PKReader

        # Create requester from private key
        requester = PKReader(
            service_account_private_key_file_name="path/to/private_key.pem",
            service_account_id="your-service-account-id",
            service_account_public_key_id="your-public-key-id",
        )

        # Create a future for the channel that will be resolved with the SDK
        channel_future = Future()

        sdk = SDK(credentials=Bearer(requester=requester, channel=channel_future))

        # Resolve the future with the newly created SDK
        channel_future.set_result(sdk)
    """

    def __init__(
        self,
        requester: TokenRequester,
        channel: ClientChannelInterface | DeferredChannel | None = None,
        max_retries: int = 2,
    ) -> None:
        """Create an exchangeable bearer."""
        super().__init__()
        self._requester = requester
        self._max_retries = max_retries

        self._svc: (
            TokenExchangeServiceClient
            | Coroutine[Any, Any, TokenExchangeServiceClient]
            | None
        ) = None
        self.set_channel(channel)

    def set_channel(
        self,
        channel: ClientChannelInterface | DeferredChannel | None,
    ) -> None:
        """Set the gRPC channel or awaitable channel used for exchanges.

        The function accepts either a concrete :class:`ClientChannelInterface`
        or an awaitable resolving to one. When an awaitable is supplied,
        the bearer lazily constructs a stub coroutine that awaits the
        channel and then constructs the :class:`TokenExchangeServiceClient`.

        :param channel: The channel or awaitable resolving to a channel.
        """
        if isinstance(channel, Awaitable):  # type: ignore[unused-ignore]

            async def token_exchange_service_stub() -> TokenExchangeServiceClient:
                chan = await channel
                if not isinstance(chan, ClientChannelInterface):  # type: ignore[unused-ignore]
                    raise TypeError(
                        f"Expected ClientChannelInterface, got {type(chan)} instead."
                    )
                return TokenExchangeServiceClient(chan)

            self._svc = token_exchange_service_stub()

        elif channel is not None:
            self._svc = TokenExchangeServiceClient(channel)
        else:
            self._svc = None

    def receiver(self) -> Receiver:
        """Return a :class:`Receiver` that performs exchanges.

        :raises ValueError: if no channel has been configured on the
            bearer.
        :returns: A :class:`Receiver` instance.
        """
        if self._svc is None:
            raise ValueError("gRPC channel is not set for the bearer.")
        return Receiver(self._requester, self._svc, max_retries=self._max_retries)
