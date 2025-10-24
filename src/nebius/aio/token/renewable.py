"""Renewable token bearer and receiver.

This module implements a wrapper around an existing asynchronous
``Bearer`` that provides automatic background token refresh and a
light-weight per-request ``Receiver`` implementation which delegates the
actual token fetch to the wrapped bearer while supporting retry accounting.

The primary public types provided here are:

- :class:`Receiver` -- per-request receiver that calls the parent
    bearer to obtain a token and tracks retry attempts.
- :class:`Bearer` -- a bearer that wraps another bearer and keeps a
    cached token refreshed in the background. It provides synchronous and
    asynchronous renewal request modes and convenient shutdown semantics.

Notes
-----
The renewal bearer starts a background task on the first token fetch
and keeps the cached token refreshed up to a configurable safe fraction
of the token lifetime. When a fetch request requires a renewed token
it may either wait for the renewal to complete (synchronous mode) or
trigger a background renewal and wait for the cached token to become
fresh (asynchronous mode).

Examples
--------
Basic usage (asynchronous renewal):

::

    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.aio.token.renewable import Bearer as RenewableBearer
    import asyncio

    async def demo():
        src = StaticBearer("my-static-token")
        bearer = RenewableBearer(src)
        receiver = bearer.receiver()
        tok = await receiver.fetch(timeout=5)
        print(tok)

    asyncio.run(demo())

Synchronous renewal request (waits for a fresh token, raising on
timeout):

::

    from nebius.aio.token.static import Bearer as StaticBearer
    from nebius.aio.token.renewable import Bearer as RenewableBearer
    from nebius.aio.token.renewable import (
        OPTION_RENEW_SYNCHRONOUS,
        OPTION_RENEW_REQUEST_TIMEOUT,
    )
    import asyncio

    async def sync_demo():
        src = StaticBearer("my-static-token")
        bearer = RenewableBearer(src)
        receiver = bearer.receiver()
        options = {
            OPTION_RENEW_SYNCHRONOUS: "1",
            OPTION_RENEW_REQUEST_TIMEOUT: "2.0",
        }
        tok = await receiver.fetch(timeout=5, options=options)
        print(tok)

    asyncio.run(sync_demo())
"""

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
    """Base exception raised for renewal-related failures.

    This exception is used to signal errors that occur during token
    renewal operations managed by :class:`Bearer`.
    """


class IsStoppedError(RenewalError):
    """Raised when a renewal operation is requested but the bearer is already stopped.

    The exception has no additional attributes; it simply indicates that
    the background renewal machinery has been shut down and cannot perform
    further renewals.
    """

    def __init__(self) -> None:
        """Create the error with a suitable message."""
        super().__init__("Renewal is stopped.")


class Receiver(ParentReceiver):
    """Per-request receiver that delegates fetching to the parent
    renewable bearer while accounting for retry attempts.

    The receiver tracks the number of fetch attempts for a single
    request. On transient failures it can instruct the parent bearer to
    schedule a background renewal (unless a synchronous renewal was
    requested via options).

    Example
    -------

    ::

        receiver = bearer.receiver()
        token = await receiver.fetch(timeout=5)

    :param parent: The :class:`Bearer` instance that performs background token
        fetch and renewal.
    :param max_retries: Maximum number of automatic retry attempts
        this receiver will allow before giving up.
    """

    def __init__(
        self,
        parent: "Bearer",
        max_retries: int = 2,
    ) -> None:
        """Create a receiver bound to the given renewable bearer."""
        super().__init__()
        self._parent = parent
        self._max_retries = max_retries
        self._trial = 0

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Fetch a token by delegating to the parent bearer.

        This method increments the internal trial counter which is used by
        :meth:`can_retry` to decide whether further retries are permitted.

        :param timeout: Optional timeout in seconds forwarded to the
            parent's fetch implementation.
        :param options: Optional request-specific options forwarded to
            the parent bearer.
        :returns: The fetched :class:`Token`.
        """
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
        """Decide whether a failed fetch should be retried.

        The decision is based on the configured maximum retry count and an
        optional :data:`OPTION_RENEW_SYNCHRONOUS` option which disables
        background renewal triggering.

        :param err: The exception raised by the failed fetch (unused but
            provided for API compatibility).
        :param options: Optional mapping of request options that may
            contain an override for :data:`OPTION_MAX_RETRIES` or the
            synchronous renewal flag.
        :returns: `True` when another retry should be attempted,
            `False` otherwise.
        """
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
            # instruct parent to schedule a background renewal
            self._parent.request_renewal()
        return True


T = TypeVar("T")


VERY_LONG_TIMEOUT = timedelta(days=365 * 10)  # 10 years, should be enough for anyone
"""If the timeout is not specified, this value will be used as the default."""


class Bearer(ParentBearer):
    """Bearer that keeps a shared cached token refreshed in the background.

    The :class:`Bearer` wraps another :class:`ParentBearer` and starts a
    background task on the first fetch. The cached token is refreshed
    proactively based on the token's expiration and the configured
    ``lifetime_safe_fraction``.

    The bearer supports two renewal modes for fetch requests:
        - asynchronous: trigger a background renewal and wait for the
            cached token to become fresh;
        - synchronous: block until a new token has been fetched (or until
            a specified request timeout elapses).

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from nebius.sdk import SDK
        from nebius.aio.token.renewable import Bearer
        from nebius.aio.token.static import Bearer as StaticBearer

        some_bearer = StaticBearer("my-static-token") # for illustrative purposes

        # Wrap some bearer with renewal
        renewable_bearer = Bearer(some_bearer)

        sdk = SDK(credentials=renewable_bearer)

    :param source: The inner bearer used to actually fetch tokens.
    :param max_retries: Maximum number of retry attempts performed by
        receivers created by :meth:`receiver`.
    :param lifetime_safe_fraction: Fraction of remaining token
        lifetime after which a refresh will be scheduled (e.g.
        ``0.9`` refreshes when 90% of lifetime has passed).
    :param initial_retry_timeout: Initial retry delay used in a backoff when a
        refresh fails.
    :param max_retry_timeout: Maximum retry delay cap.
    :param retry_timeout_exponent: Exponential backoff base used to
        grow retry delays between attempts.
    :param refresh_request_timeout: Timeout used for individual
        refresh requests when contacting the inner bearer.
    """

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
        """Initialize the renewable bearer."""
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
        """Run a coroutine without awaiting or tracking, and log exceptions.

        The coroutine is scheduled as a background task and any
        unhandled exception is logged. The returned task is tracked so it
        can be cancelled during shutdown.

        :param coro: Awaitable to run in a fire-and-forget task.
        :returns: The created :class:`asyncio.Task` instance.
        """

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
        """Fetch a token, renewing it if necessary.

        The fetch operation may trigger a background renewal or perform a
        synchronous renewal based on the provided ``options``. When a
        synchronous renewal is requested the caller waits for a new token
        to be fetched (or for the request timeout to expire).

        :param timeout: Optional timeout in seconds for waiting for a token.
        :param options: Optional mapping of request flags. Recognized
            keys include:

              - :data:`OPTION_RENEW_REQUIRED`: force a renewal
              - :data:`OPTION_RENEW_SYNCHRONOUS`: request synchronous renewal
              - :data:`OPTION_RENEW_REQUEST_TIMEOUT`: override synchronous
                  renewal request timeout (as a string float)
              - :data:`OPTION_REPORT_ERROR`: return errors from renewal to the
                  caller via an exception

        :returns: A fresh :class:`Token` instance.
        :raises RenewalError: when the cache remains empty after renewal.
        """
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
        """Fetch a single token from the inner bearer.

        This helper performs a single attempt to obtain a token from
        ``self._source`` while cooperating with the synchronous-renewal
        signalling primitives. It returns the received token and updates
        the cached token on success.
        """
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
        """Background loop that refreshes the token periodically.

        The loop waits either until a scheduled retry timeout elapses or
        until an explicit renewal request is signalled. On errors a backoff
        strategy is applied before the next attempt.
        """
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
        """Close the bearer, cancelling background tasks and closing source.

        :param grace: Optional graceful shutdown timeout forwarded to the
            inner bearer's :meth:`close` method.
        """
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
        """Return ``True`` when a renewal should be performed.

        Renewal is required when there is no cached token or when an
        explicit renewal request has been signalled.
        """
        return self._cache is None or self._renew_requested.is_set()

    def request_renewal(self) -> None:
        """Request a token renewal.

        If the bearer is not stopped this clears the freshness flag and
        signals the background loop to perform a renewal as soon as
        possible.
        """
        if not self._is_stopped.is_set():
            log.debug("token renewal requested")
            self._is_fresh.clear()
            self._renew_requested.set()

    def stop(self) -> None:
        """Stop the renewal background task and unblock any waiters.

        This method marks the bearer as stopped, clears the freshness
        event and signals any waiting synchronous renewal attempts to
        unblock. It is safe to call multiple times.
        """
        log.debug("stopping renewal task")
        self._is_stopped.set()
        self._is_fresh.clear()
        self._break_previous_attempt.set()
        self._renew_requested.set()

    def receiver(self) -> Receiver:
        """Return a per-request :class:`Receiver` bound to this bearer.

        The returned receiver will use the bearer's configuration for retry behaviour.
        :returns: A :class:`Receiver` instance.
        """
        return Receiver(self, max_retries=self._max_retries)
