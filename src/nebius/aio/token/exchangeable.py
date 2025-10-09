from collections.abc import Awaitable, Coroutine
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

from grpc.aio import AioRpcError
from grpc.aio import Channel as GRPCChannel
from grpc.aio._metadata import Metadata
from grpc_status import rpc_status

from nebius.aio.token.deferred_channel import DeferredChannel
from nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc import (
    TokenExchangeServiceStub,
)
from nebius.api.nebius.iam.v1.token_service_pb2 import CreateTokenResponse
from nebius.base.error import SDKError
from nebius.base.metadata import Authorization, Internal
from nebius.base.metadata import Metadata as NebiusMetadata
from nebius.base.service_account.service_account import TokenRequester
from nebius.base.token_sanitizer import TokenSanitizer

from .options import OPTION_MAX_RETRIES
from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

sanitizer = TokenSanitizer.access_token_sanitizer()

log = getLogger(__name__)


class UnsupportedResponseError(SDKError):
    def __init__(self, expected: str, resp: Any) -> None:
        super().__init__(
            f"Unsupported response received: expected {expected},"
            f" received {type(resp)}"
        )


class UnsupportedTokenTypeError(SDKError):
    def __init__(self, token_type: str) -> None:
        super().__init__(
            "Unsupported token received: expected Bearer," f" received {token_type}"
        )


class Receiver(ParentReceiver):
    def __init__(
        self,
        requester: TokenRequester,
        service: TokenExchangeServiceStub | Awaitable[TokenExchangeServiceStub],
        max_retries: int = 2,
    ) -> None:
        super().__init__()
        self._requester = requester
        self._svc = service
        self._max_retries = max_retries

        self._trial = 0

    def _raise_request_error(self, err: AioRpcError) -> None:
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
        self._trial += 1
        req = self._requester.get_exchange_token_request()

        now = datetime.now(timezone.utc)

        md = Metadata()
        md.add(Internal.AUTHORIZATION.lower(), Authorization.DISABLE)

        log.debug(f"fetching new token, attempt: {self._trial}, timeout: {timeout}")

        ret = None
        try:
            if isinstance(self._svc, Awaitable):
                self._svc = await self._svc
            ret = await self._svc.Exchange(req, metadata=md, timeout=timeout)  # type: ignore[unused-ignore]
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
    def __init__(
        self,
        requester: TokenRequester,
        channel: GRPCChannel | DeferredChannel | None = None,
        max_retries: int = 2,
    ) -> None:
        super().__init__()
        self._requester = requester
        self._max_retries = max_retries

        self._svc: (
            TokenExchangeServiceStub
            | Coroutine[Any, Any, TokenExchangeServiceStub]
            | None
        ) = None
        self.set_channel(channel)

    def set_channel(self, channel: GRPCChannel | DeferredChannel | None) -> None:
        """
        Set the gRPC channel for the bearer.
        """
        if isinstance(channel, Awaitable):  # type: ignore[unused-ignore]

            async def token_exchange_service_stub() -> TokenExchangeServiceStub:
                chan = await channel
                if not isinstance(chan, GRPCChannel):  # type: ignore[unused-ignore]
                    raise TypeError(f"Expected GRPCChannel, got {type(chan)} instead.")
                return TokenExchangeServiceStub(chan)  # type: ignore

            self._svc = token_exchange_service_stub()

        elif channel is not None:
            self._svc = TokenExchangeServiceStub(channel)  # type:ignore
        else:
            self._svc = None

    def receiver(self) -> Receiver:
        if self._svc is None:
            raise ValueError("gRPC channel is not set for the bearer.")
        return Receiver(self._requester, self._svc, max_retries=self._max_retries)
