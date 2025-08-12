import sys
from asyncio import (
    FIRST_COMPLETED,
    CancelledError,
    Event,
    Future,
    Task,
    create_task,
    gather,
    sleep,
    wait,
    wait_for,
)
from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any, TypeVar

from nebius.base.error import SDKError

from .options import (
    OPTION_MAX_RETRIES,
    OPTION_RENEW_REQUEST_TIMEOUT,
    OPTION_RENEW_REQUIRED,
    OPTION_RENEW_SYNCHRONOUS,
    OPTION_REPORT_ERROR,
)
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

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        self._trial += 1
        log.debug(
            f"token fetch requested, attempt: {self._trial}," f"timeout: {timeout}"
        )
        return await self._parent.fetch(timeout=timeout, options=options)

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        max_retries = self._max_retries
        synchronous = False
        if options is not None:
            synchronous = options.get(OPTION_RENEW_SYNCHRONOUS, "") != ""
            if OPTION_MAX_RETRIES in options:
                value = options[OPTION_MAX_RETRIES]
                try:
                    max_retries = int(value)
                except ValueError as val_err:
                    log.error(
                        f"option {OPTION_MAX_RETRIES} is not valid integer: {val_err=}"
                    )
        if self._trial >= max_retries:
            log.debug("max retries reached, cannot retry")
            return False
        if not synchronous:
            self._parent.request_renewal()
        return True


T = TypeVar("T")


VERY_LONG_TIMEOUT = timedelta(days=365 * 10)  # 10 years, should be enough for anyone


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
        self._synchronous_can_proceed = Event()
        self._break_previous_attempt = Event()

        self._synchronous_can_proceed.set()

        self._refresh_task: Task[Any] | None = None
        self._tasks = set[Task[Any]]()

        self._renewal_attempt = 0

        self._max_retries = max_retries
        self._lifetime_safe_fraction = lifetime_safe_fraction
        self._initial_retry_timeout = initial_retry_timeout
        self._max_retry_timeout = max_retry_timeout
        self._retry_timeout_exponent = retry_timeout_exponent
        self._refresh_request_timeout = refresh_request_timeout

        self._renew_synchronous_timeout: float | None = None
        self._renewal_future: Future[Token] | None = None
        self._renew_synchronous_options: dict[str, str] | None = None

    @property
    def wrapped(self) -> ParentBearer | None:
        """Return the wrapped bearer."""
        return self._source

    def bg_task(self, coro: Awaitable[T]) -> Task[None]:
        """Run a coroutine without awaiting or tracking, and log any exceptions."""

        async def wrapper() -> None:
            try:
                await coro
            except CancelledError:
                pass
            except Exception as e:
                log.error("Unhandled exception in fire-and-forget task", exc_info=e)

        ret = create_task(wrapper())
        ret.add_done_callback(lambda x: self._tasks.discard(x))
        self._tasks.add(ret)
        return ret

    async def fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        required = False
        synchronous = False
        report_error = False
        if options is not None:
            required = options.get(OPTION_RENEW_REQUIRED, "") != ""
            synchronous = options.get(OPTION_RENEW_SYNCHRONOUS, "") != ""
            report_error = options.get(OPTION_REPORT_ERROR, "") != ""

        if self._refresh_task is None:
            log.debug("no refresh task yet, starting it")
            self._refresh_task = self.bg_task(self._run())
        if self.is_renewal_required() or required:
            log.debug(f"renewal required, timeout {timeout}")
            if synchronous:
                self._break_previous_attempt.set()
                await wait_for(self._synchronous_can_proceed.wait(), timeout)
                if OPTION_RENEW_REQUEST_TIMEOUT in options:  # type: ignore
                    try:
                        self._renew_synchronous_timeout = float(
                            options[OPTION_RENEW_REQUEST_TIMEOUT]  # type: ignore
                        )
                    except ValueError as err:
                        log.error(
                            f"option {OPTION_RENEW_REQUEST_TIMEOUT} value is not float:"
                            f" {err=}"
                        )
                self._renew_synchronous_options = options.copy()  # type: ignore
            if report_error or synchronous:
                self._renewal_future = Future[Token]()

            self._renew_requested.set()
            if report_error or synchronous:
                return await wait_for(self._renewal_future, timeout)  # type: ignore
            else:
                await wait_for(self._is_fresh.wait(), timeout)
        if self._cache is None:
            raise RenewalError("cache is empty after renewal")
        return self._cache

    async def _fetch_once(self) -> Token:
        tok = None
        log.debug(f"refreshing token, attempt {self._renewal_attempt}")
        self._break_previous_attempt.clear()
        self._synchronous_can_proceed.clear()
        timeout = self._refresh_request_timeout.total_seconds()
        if self._renew_synchronous_timeout is not None:
            timeout = self._renew_synchronous_timeout
            self._renew_synchronous_timeout = None
        token_task = create_task(self._source.receiver().fetch(timeout))
        breaker_task = create_task(self._break_previous_attempt.wait())
        _done, pending = await wait(
            [token_task, breaker_task],
            return_when=FIRST_COMPLETED,
        )
        self._renew_requested.clear()
        self._synchronous_can_proceed.set()
        for t in pending:
            t.cancel()
            self.bg_task(t)
        tok = token_task.result()
        log.debug(f"received new token: {tok}")
        if self._renewal_future is not None and not self._renewal_future.done():
            self._renewal_future.set_result(tok)
        self._cache = tok
        self._renewal_attempt = 0
        self._is_fresh.set()
        return tok

    async def _run(self) -> None:
        log.debug("refresh task started")
        while not self._is_stopped.is_set():
            try:
                tok = await self._fetch_once()
                exp = tok.expiration
                if exp is None:
                    retry_timeout = VERY_LONG_TIMEOUT.total_seconds()
                else:
                    retry_timeout = (
                        exp - datetime.now(timezone.utc)
                    ).total_seconds() * self._lifetime_safe_fraction
            except Exception as e:
                log.error(
                    f"Failed refresh token, attempt: {self._renewal_attempt}, "
                    f"error: {e}",
                    exc_info=sys.exc_info(),
                )
                if self._renewal_future is not None and not self._renewal_future.done():
                    self._renewal_future.set_exception(e)
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
            _done, pending = await wait(
                [
                    self.bg_task(self._renew_requested.wait()),
                    self.bg_task(sleep(retry_timeout)),
                ],
                return_when=FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            await gather(*pending, return_exceptions=True)

    async def close(self, grace: float | None = None) -> None:
        source_close = create_task(self._source.close(grace=grace))
        self.stop()
        for task in self._tasks:
            task.cancel()
        rets = await gather(
            source_close,
            *self._tasks,
            return_exceptions=True,
        )
        for ret in rets:
            if isinstance(ret, BaseException) and not isinstance(ret, CancelledError):
                log.error(f"Error while graceful shutdown: {ret}", exc_info=ret)

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
        self._break_previous_attempt.set()
        self._renew_requested.set()

    def receiver(self) -> Receiver:
        return Receiver(self, max_retries=self._max_retries)
