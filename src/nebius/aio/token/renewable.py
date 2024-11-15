import sys
from asyncio import Event, Task, wait_for
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

from nebius.base.error import SDKError
from nebius.base.sanitization import ellipsis_in_middle

from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

log = getLogger(__name__)


class RenewalError(SDKError):
    pass


class IsStoppedError(RenewalError):
    def __init__(self) -> None:
        super().__init__("Renewal is stopped.")


class Receiver(ParentReceiver):
    def __init__(
        self,
        parent: "Bearer",
        max_retries: int = 2,
    ) -> None:
        super().__init__()
        self._parent = parent
        self._max_retries = max_retries
        self._trial = 0

    async def _fetch(self, timeout: float | None = None) -> Token:
        self._trial += 1
        log.debug(
            f"token fetch requested, attempt: {self._trial}," f"timeout: {timeout}"
        )
        return await self._parent.fetch(timeout=timeout)

    def can_retry(self, err: Exception) -> bool:
        if self._trial >= self._max_retries:
            log.debug("max retries reached, cannot retry")
            return False
        self._parent.request_renewal()
        return True


class Bearer(ParentBearer):
    def __init__(
        self,
        source: ParentBearer,
        max_retries: int = 2,
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        refresh_request_timeout: timedelta = timedelta(seconds=5),
    ) -> None:
        super().__init__()
        self._source = source
        self._cache: Token | None = None

        self._is_fresh = Event()
        self._is_stopped = Event()
        self._renew_requested = Event()

        self._refresh_task: Task[Any] | None = None

        self._renewal_attempt = 0

        self._max_retries = max_retries
        self._lifetime_safe_fraction = lifetime_safe_fraction
        self._initial_retry_timeout = initial_retry_timeout
        self._max_retry_timeout = max_retry_timeout
        self._retry_timeout_exponent = retry_timeout_exponent
        self._refresh_request_timeout = refresh_request_timeout

    async def fetch(self, timeout: float | None = None) -> Token:
        if self._refresh_task is None:
            log.debug("no refresh task yet, starting it")
            self._refresh_task = Task(self._run())
        if self.is_renewal_required():
            log.debug(f"renewal required, timeout {timeout}")
            if timeout is not None:
                await wait_for(self._is_fresh.wait(), timeout)
            else:
                await self._is_fresh.wait()
        if self._cache is None:
            raise RenewalError("cache is empty after renewal")
        return self._cache

    async def _run(self) -> None:
        log.debug("refresh task started")
        while not self._is_stopped.is_set():
            self._renew_requested.set()
            self._renewal_attempt += 1
            tok = None
            log.debug(f"refreshing token, attempt {self._renewal_attempt}")
            try:
                tok = await self._source.receiver().fetch(
                    self._refresh_request_timeout.total_seconds(),
                )
                log.debug(
                    f"received new token: {ellipsis_in_middle(tok.token)}, "
                    f"expires in {tok.expiration}"
                )
            except Exception as e:
                log.error(
                    f"Failed refresh token, attempt: {self._renewal_attempt}, "
                    f"error: {e}",
                    exc_info=sys.exc_info(),
                )
            self._renew_requested.clear()
            if tok is not None:
                self._cache = tok
                self._renewal_attempt = 0
                self._is_fresh.set()
                retry_timeout = (
                    tok.expiration - datetime.now(timezone.utc)
                ).total_seconds() * self._lifetime_safe_fraction
            else:
                if (
                    self._renewal_attempt <= 1
                    or abs(self._retry_timeout_exponent - 1) < 1e-9
                ):
                    retry_timeout = self._initial_retry_timeout.total_seconds()
                else:
                    mul = self._retry_timeout_exponent ** (self._renewal_attempt - 1)
                    retry_timeout = min(
                        self._initial_retry_timeout.total_seconds() * mul,
                        self._max_retry_timeout.total_seconds(),
                    )
            if retry_timeout < self._initial_retry_timeout.total_seconds():
                retry_timeout = self._initial_retry_timeout.total_seconds()

            log.debug(
                f"Will refresh token after {retry_timeout} seconds, "
                f"renewal attempt number {self._renewal_attempt}"
            )
            await wait_for(self._renew_requested.wait(), retry_timeout)

    def is_renewal_required(self) -> bool:
        return self._cache is None or self._renew_requested.is_set()

    def request_renewal(self) -> None:
        if not self._is_stopped.is_set():
            log.debug("token renewal requested")
            self._is_fresh.clear()
            self._renew_requested.set()

    def stop(self) -> None:
        log.debug("stopping renewal task")
        self._is_stopped.set()
        self._is_fresh.clear()
        self._renew_requested.set()

    def receiver(self) -> Receiver:
        return Receiver(self, max_retries=self._max_retries)
