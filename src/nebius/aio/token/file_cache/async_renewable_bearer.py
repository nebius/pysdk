"""Asynchronous renewable file-backed bearer.

This module provides an asynchronous variant of the renewable file-backed
bearer which uses a :class:`ThrottledTokenCache` and runs a background
refresh task. The implementation exposes two primary classes:

- :class:`AsynchronousRenewableFileCacheReceiver` -- An async receiver that
    prefers the cached token when it's fresh and, when required, requests a
    renewal from the wrapped bearer. It implements a limited retry strategy.
- :class:`AsynchronousRenewableFileCacheBearer` -- A bearer that wraps an
    existing :class:`nebius.aio.token.token.Bearer` and manages a background
    refresh loop that persists tokens to a file-backed cache.

Example
-------

Create an asynchronous renewable bearer from a named network bearer::

        async_bearer = AsynchronousRenewableFileCacheBearer(network_bearer)
        token = await async_bearer.receiver().fetch()

"""

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
from pathlib import Path
from typing import Any, TypeVar

from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import Receiver as ParentReceiver
from nebius.aio.token.token import Token
from nebius.base.constants import DEFAULT_CONFIG_DIR, DEFAULT_CREDENTIALS_FILE

from ..options import (
    OPTION_MAX_RETRIES,
    OPTION_RENEW_REQUEST_TIMEOUT,
    OPTION_RENEW_REQUIRED,
    OPTION_RENEW_SYNCHRONOUS,
    OPTION_REPORT_ERROR,
)
from ..renewable import (
    RenewalError,
)
from .throttled_token_cache import ThrottledTokenCache

log = getLogger(__name__)


class AsynchronousRenewableFileCacheReceiver(ParentReceiver):
    """Receiver that requests asynchronous renewals when needed.

    The receiver delegates to the parent :class:`AsynchronousRenewableFileCacheBearer`
    for actual fetching and renewal coordination. It tracks a small retry
    counter so transient errors can be retried a configurable number of times.

    Example
    -------

    Constructing a receiver is normally done via the bearer's
    :meth:`AsynchronousRenewableFileCacheBearer.receiver` method::

        receiver = async_bearer.receiver()

    :param bearer: The owning :class:`AsynchronousRenewableFileCacheBearer`.
    :param max_retries: Maximum number of automatic retry attempts before
        giving up.
    """

    def __init__(
        self,
        bearer: "AsynchronousRenewableFileCacheBearer",
        max_retries: int = 2,
    ) -> None:
        """Initialize the receiver.

        No I/O is performed during construction.
        """
        super().__init__()
        self._parent = bearer
        self._max_retries = max_retries
        self._trial = 0

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Fetch a token, forwarding to the parent bearer.

        The method increments an internal trial count used by
        :meth:`can_retry` and delegates the actual fetch to the parent
        bearer's :meth:`AsynchronousRenewableFileCacheBearer.fetch` method.

        :param timeout: Optional timeout forwarded to the parent fetch.
        :param options: Optional fetch options forwarded to the parent.
        :returns: A :class:`Token` instance.
        """
        self._trial += 1
        log.debug(f"token fetch requested, attempt: {self._trial},timeout: {timeout}")
        return await self._parent.fetch(timeout=timeout, options=options)

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Decide whether the caller should retry the operation.

        The receiver inspects provided options and the internal trial count to
        decide whether to allow another retry. When retries are permitted and
        the operation was not requested synchronously the receiver will
        proactively request a background renewal via the parent bearer.

        :param err: The exception that occurred during fetch.
        :param options: Optional map of string options. Supported keys include
            :data:`OPTION_RENEW_SYNCHRONOUS` and :data:`OPTION_MAX_RETRIES` which can
            override synchronous behavior and the max retry count.
        :returns: `True` if the caller should retry, `False` otherwise.
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
            # Proactively request an asynchronous renewal so other callers
            # may receive a fresh token.
            self._parent.request_renewal()
        return True


VERY_LONG_TIMEOUT = timedelta(days=365 * 10)  # 10 years, should be enough for anyone

"""A very long timeout used when a token has no expiration.

This constant is used as an effectively infinite timeout value when
calculating retry intervals for tokens that carry no expiration time.
"""

T = TypeVar("T")


class AsynchronousRenewableFileCacheBearer(ParentBearer):
    """Asynchronous bearer that refreshes tokens into a file-backed cache.

    This bearer wraps a network-facing :class:`nebius.aio.token.token.Bearer`
    and uses a :class:`ThrottledTokenCache` for persistence. A background
    task may be spawned to proactively refresh the token before expiry. The
    class exposes control methods such as :meth:`request_renewal`,
    :meth:`stop` and :meth:`close` to coordinate lifecycle and shutdown.

    :ivar safety_margin: A :class:`datetime.timedelta` or seconds value used to
        determine when a token is considered too close to expiry. When ``None``
        the cache will be used until tokens are actually expired.

    :param source: Wrapped bearer used to obtain fresh tokens. The source
        must have a non-empty :attr:`nebius.aio.token.token.Bearer.name` used as the
        cache key.
    :param max_retries: Default maximum retries for receivers produced by
        :meth:`receiver`.
    :param initial_safety_margin: Safety margin before token expiration used
        for the first fetch. The token will be immediately refreshed if the
        cache token is closer to expiry than this margin.
    :param retry_safety_margin: Safety margin applied when computing the
        initial retry interval for the background loop.
    :param lifetime_safe_fraction: Fraction of the token lifetime used to
        schedule proactive refreshes (e.g. 0.9 means refresh at 90% of life).
    :param initial_retry_timeout: Initial retry backoff timeout used after failures.
    :param max_retry_timeout: Maximum retry backoff timeout used when backing off.
    :param retry_timeout_exponent: Exponent used for exponential backoff.
    :param refresh_request_timeout: Default timeout forwarded to the
        wrapped receiver during refresh operations.
    :param file_cache_throttle: Throttle interval passed to
        :class:`ThrottledTokenCache` to reduce disk reads.

    Example
    -------

    Wrap a custom bearer with a name and file cache::

        from nebius.sdk import SDK
        from nebius.aio.token.token import NamedBearer, Bearer, Receiver, Token
        from nebius.aio.token.file_cache.async_renewable_bearer import (
            AsynchronousRenewableFileCacheBearer
        )

        class SomeCustomHeavyLoadBearer(Bearer):
            def receiver(self) -> Receiver:
                return SomeReceiver()

        class SomeReceiver(Receiver):
            async def _fetch(self, timeout=None, options=None) -> Token:
                # Simulate heavy load token fetch
                return Token("heavy-token")

            def can_retry(self, err, options=None) -> bool:
                return False

        custom_bearer = SomeCustomHeavyLoadBearer()
        named_bearer = NamedBearer(custom_bearer, "heavy-load-bearer")
        cached_bearer = AsynchronousRenewableFileCacheBearer(named_bearer)

        sdk = SDK(credentials=cached_bearer)
    """

    def __init__(
        self,
        source: ParentBearer,
        max_retries: int = 2,
        initial_safety_margin: timedelta | float | None = timedelta(hours=2),
        retry_safety_margin: timedelta = timedelta(hours=2),
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        refresh_request_timeout: timedelta = timedelta(seconds=5),
        file_cache_throttle: timedelta | float = timedelta(minutes=5),
    ) -> None:
        """Initialize the asynchronous renewable bearer.

        The constructor constructs a :class:`ThrottledTokenCache` using the
        source bearer's :attr:`nebius.aio.token.token.Bearer.name` and prepares internal
        synchronization primitives used by the background refresh loop.

        :raises ValueError: When the wrapped bearer has no name.
        """
        super().__init__()
        self._source = source
        if isinstance(initial_safety_margin, (float, int)):
            initial_safety_margin = timedelta(seconds=initial_safety_margin)
        self._retry_safety_margin = retry_safety_margin
        self.safety_margin = initial_safety_margin
        name = self._source.name
        if name is None:
            raise ValueError("Source bearer must have a name for the cache.")
        self._file_cache = ThrottledTokenCache(
            name=name,
            cache_file=Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
            throttle=file_cache_throttle,
        )

        # Synchronization and lifecycle events used by the refresh loop.
        self._is_fresh = Event()
        self._is_stopped = Event()
        self._renew_requested = Event()
        self._synchronous_can_proceed = Event()
        self._break_previous_attempt = Event()

        self._synchronous_can_proceed.set()

        # Background task handles and bookkeeping.
        self._refresh_task: Task[Any] | None = None
        self._tasks = set[Task[Any]]()

        self._renewal_attempt = 0

        self._max_retries = max_retries
        self._lifetime_safe_fraction = lifetime_safe_fraction
        self._initial_retry_timeout = initial_retry_timeout
        self._max_retry_timeout = max_retry_timeout
        self._retry_timeout_exponent = retry_timeout_exponent
        self._refresh_request_timeout = refresh_request_timeout

        # Fields used when synchronous renewal requests are made by callers.
        self._renew_synchronous_timeout: float | None = None
        self._renewal_future: Future[Token] | None = None
        self._renew_synchronous_options: dict[str, str] | None = None

    @property
    def wrapped(self) -> ParentBearer | None:
        """Return the wrapped bearer instance.

        :returns: The underlying bearer provided at construction.
        """
        return self._source

    def bg_task(self, coro: Awaitable[T]) -> Task[None]:
        """Run a coroutine in fire-and-forget mode.

        The helper wraps the provided coroutine in a simple error-handling
        wrapper so exceptions are logged rather than lost. The returned
        :class:`asyncio.Task` is tracked in :attr:`_tasks` and will be
        automatically removed when done.

        :param coro: Awaitable to schedule.
        :returns: The created :class:`asyncio.Task`.
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
        """Fetch a token, using the file cache and optionally requesting renewal.

        The method attempts to return a cached token when it is considered
        fresh according to :attr:`safety_margin`. If the token is missing or
        too close to expiry a renewal is requested. The renewal may be handled
        asynchronously by the background refresh loop or synchronously if the
        caller requests it via provided options.

        Supported options
        -----------------
        - :data:`OPTION_RENEW_REQUIRED` -- Force a renewal even if a cached token
          exists.
        - :data:`OPTION_RENEW_SYNCHRONOUS` -- Request the renewal synchronously and
          wait for the result.
        - :data:`OPTION_REPORT_ERROR` -- Return exceptions from the renewal to the
          caller via the returned future.
        - :data:`OPTION_RENEW_REQUEST_TIMEOUT` -- When performing a synchronous
          request, this value (string float) can override the request timeout.

        :param timeout: Timeout in seconds for synchronous waits.
        :param options: Optional dictionary of string options (see above).
        :returns: A valid :class:`Token`.
        :raises RenewalError: If the cache is still empty after a renewal.
        """
        required = False
        synchronous = False
        report_error = False
        if options is not None:
            required = options.get(OPTION_RENEW_REQUIRED, "") != ""
            synchronous = options.get(OPTION_RENEW_SYNCHRONOUS, "") != ""
            report_error = options.get(OPTION_REPORT_ERROR, "") != ""

        tok = await self._file_cache.get()
        if not required and tok is not None and not tok.is_expired():
            if self.safety_margin is None or (
                not tok.expiration
                or (tok.expiration - self.safety_margin > datetime.now(timezone.utc))
            ):
                log.debug(f"token is fresh: {tok}")
                if self._refresh_task is None:
                    log.debug("no refresh task yet, starting it")
                    self._refresh_task = self.bg_task(self._run(True))
                return tok
        self.safety_margin = None  # reset safety margin after first fetch

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
        tok = await self._file_cache.get()
        if tok is None:
            raise RenewalError("cache is empty after renewal")
        return tok

    async def _fetch_once(self) -> Token:
        """Perform a single token refresh attempt.

        This helper arranges concurrent tasks for fetching a token from the
        wrapped bearer and for canceling that fetch if a newer synchronous
        request arrives. On success the new token is persisted into the
        file cache and any waiting synchronous future is fulfilled.

        :returns: The newly fetched :class:`Token`.
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
        await self._file_cache.set(tok)
        self._renewal_attempt = 0
        self._is_fresh.set()
        return tok

    async def _run(self, wait_for_timeout: bool = False) -> None:
        """Background refresh loop.

        The loop waits either for a renewal request event or for a timer
        indicating the next refresh time. On renewal it calls
        :meth:`_fetch_once` and updates the interval used for the next run.
        Failures are logged and the retry interval is increased using an
        exponential backoff strategy up to ``_max_retry_timeout``.

        :param wait_for_timeout: When true the loop will compute an initial wait
            interval based on the currently cached token to avoid immediate
            refreshes.
        """
        log.debug("refresh task started")

        if wait_for_timeout:
            tok = await self._file_cache.get()
            if tok is not None and not tok.is_expired():
                if tok.expiration is not None:
                    retry_timeout = (
                        tok.expiration - datetime.now(timezone.utc)
                    ).total_seconds() - self._retry_safety_margin.total_seconds()
                else:
                    retry_timeout = VERY_LONG_TIMEOUT.total_seconds()
            else:
                retry_timeout = 0
        else:
            retry_timeout = 0

        while not self._is_stopped.is_set():
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
                    exc_info=e,
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

    async def close(self, grace: float | None = None) -> None:
        """Close the bearer and shutdown background tasks.

        The method attempts a graceful shutdown by requesting the wrapped
        source to close, signalling the background loop to stop and cancelling
        any outstanding fire-and-forget tasks. Non-cancellation exceptions
        raised during shutdown are logged.

        :param grace: Optional grace period forwarded to the wrapped
            bearer's :meth:`close` method.
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
        """Return whether a renewal is required.

        A renewal is considered required when no token is available in the
        in-memory cache or when a renewal request event has been set.
        """
        return self._file_cache.get_cached() is None or self._renew_requested.is_set()

    def request_renewal(self) -> None:
        """Request a background token renewal.

        This method sets internal events so the background loop will attempt a
        refresh. If the bearer has been stopped the request is ignored.
        """
        if not self._is_stopped.is_set():
            log.debug("token renewal requested")
            self._is_fresh.clear()
            self._renew_requested.set()

    def stop(self) -> None:
        """Stop the background refresh loop and break any running attempt.

        After calling this method the bearer will not perform further
        renewals until a new instance is created. The method also clears
        fresh-state events so callers waiting for tokens will fail fast.
        """
        log.debug("stopping renewal task")
        self._is_stopped.set()
        self._is_fresh.clear()
        self._break_previous_attempt.set()
        self._renew_requested.set()

    def receiver(self) -> AsynchronousRenewableFileCacheReceiver:
        """Return a new :class:`AsynchronousRenewableFileCacheReceiver`.

        :returns: A receiver bound to this bearer which will forward fetch
            requests to the bearer and participate in the retry semantics.
        """
        return AsynchronousRenewableFileCacheReceiver(
            self,
            max_retries=self._max_retries,
        )
