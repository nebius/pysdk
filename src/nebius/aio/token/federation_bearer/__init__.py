from asyncio import Task
from datetime import datetime, timedelta, timezone
from logging import getLogger
from ssl import SSLContext
from typing import Any, TextIO, TypeVar

from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import Receiver as ParentReceiver
from nebius.aio.token.token import Token

log = getLogger(__name__)


class Receiver(ParentReceiver):
    def __init__(
        self,
        client_id: str,
        federation_endpoint: str,
        federation_id: str,
        writer: TextIO | None = None,
        no_browser_open: bool = False,
        ssl_ctx: SSLContext | None = None,
    ) -> None:
        self._client_id = client_id
        self._federation_endpoint = federation_endpoint
        self._federation_id = federation_id
        self._writer = writer
        self._no_browser_open = no_browser_open
        self._ssl_ctx = ssl_ctx

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        from .auth import authorize

        now = datetime.now(timezone.utc)
        tok = await authorize(
            client_id=self._client_id,
            federation_endpoint=self._federation_endpoint,
            federation_id=self._federation_id,
            writer=self._writer,
            no_browser_open=self._no_browser_open,
            timeout=timeout,
            ssl_ctx=self._ssl_ctx,
        )
        return Token(
            token=tok.access_token,
            expiration=(
                now + timedelta(seconds=tok.expires_in)
                if tok.expires_in is not None
                else None
            ),
        )

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        return True


T = TypeVar("T")


class Bearer(ParentBearer):
    def __init__(
        self,
        profile_name: str,
        client_id: str,
        federation_endpoint: str,
        federation_id: str,
        writer: TextIO | None = None,
        no_browser_open: bool = False,
        ssl_ctx: SSLContext | None = None,
    ) -> None:
        self._profile_name = profile_name
        self._client_id = client_id
        self._federation_endpoint = federation_endpoint
        self._federation_id = federation_id
        self._writer = writer
        self._no_browser_open = no_browser_open
        self._ssl_ctx = ssl_ctx

        self._tasks = set[Task[Any]]()

    @property
    def name(self) -> str:
        return (
            f"federation/{self._federation_endpoint}/{self._federation_id}/"
            f"{self._profile_name}"
        )

    def receiver(self) -> ParentReceiver:
        return Receiver(
            client_id=self._client_id,
            federation_endpoint=self._federation_endpoint,
            federation_id=self._federation_id,
            writer=self._writer,
            no_browser_open=self._no_browser_open,
            ssl_ctx=self._ssl_ctx,
        )
