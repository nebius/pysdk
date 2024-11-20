from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

from grpc.aio import Channel as GRPCChannel
from grpc.aio._metadata import Metadata

from nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc import (
    TokenExchangeServiceStub,
)
from nebius.api.nebius.iam.v1.token_service_pb2 import CreateTokenResponse
from nebius.base.error import SDKError
from nebius.base.metadata import Authorization, Internal
from nebius.base.sanitization import ellipsis_in_middle
from nebius.base.service_account.service_account import TokenRequester

from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

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
        service: TokenExchangeServiceStub,
        max_retries: int = 2,
    ) -> None:
        super().__init__()
        self._requester = requester
        self._svc = service
        self._max_retries = max_retries

        self._trial = 0

    async def _fetch(self, timeout: float | None = None) -> Token:
        self._trial += 1
        req = self._requester.get_exchange_token_request()

        now = datetime.now(timezone.utc)

        md = Metadata()
        md.add(Internal.AUTHORIZATION, Authorization.DISABLE)

        log.debug(f"fetching new token, attempt: {self._trial}, timeout: {timeout}")

        ret = await self._svc.Exchange(req, metadata=md, timeout=timeout)  # type: ignore[unused-ignore]
        if not isinstance(ret, CreateTokenResponse):
            raise UnsupportedResponseError(CreateTokenResponse.__name__, ret)

        if ret.token_type != "Bearer":  # noqa: S105 — not a password
            raise UnsupportedTokenTypeError(ret.token_type)

        log.debug(
            f"token fetched: {ellipsis_in_middle(ret.access_token)},"
            f" expires in: {ret.expires_in} seconds."
        )
        return Token(
            token=ret.access_token, expiration=now + timedelta(seconds=ret.expires_in)
        )

    def can_retry(self, err: Exception) -> bool:
        if self._trial >= self._max_retries:
            log.debug("token max retries reached, cannot retry")
            return False
        return True


class Bearer(ParentBearer):
    def __init__(
        self,
        requester: TokenRequester,
        channel: GRPCChannel,
        max_retries: int = 2,
    ) -> None:
        super().__init__()
        self._requester = requester
        self._max_retries = max_retries
        self._svc = TokenExchangeServiceStub(channel)  # type:ignore

    def receiver(self) -> Receiver:
        return Receiver(self._requester, self._svc, max_retries=self._max_retries)
