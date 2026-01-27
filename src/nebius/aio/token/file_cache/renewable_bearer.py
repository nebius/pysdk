"""A renewable file-backed bearer.

This module composes a wrapped network :class:`nebius.aio.token.token.Bearer` with a
:class:`ThrottledTokenCache` to provide cached tokens that are refreshed from
the wrapped bearer when the cached token is close to expiration.

Classes
-------

- :class:`RenewableFileCacheReceiver` -- A receiver that prefers the cached
  token when it's fresh, otherwise fetches a new token from the wrapped
  bearer and stores it in the cache.
- :class:`RenewableFileCacheBearer` -- A bearer that composes an existing
  :class:`nebius.aio.token.token.Bearer` instance with a file-backed cache and exposes
  the renewable receiver.

"""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path

from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import Receiver as ParentReceiver
from nebius.aio.token.token import Token
from nebius.base.constants import DEFAULT_CONFIG_DIR, DEFAULT_CREDENTIALS_FILE

from .throttled_token_cache import ThrottledTokenCache

log = getLogger(__name__)


class RenewableFileCacheReceiver(ParentReceiver):
    """Receiver that returns a cached token when safe, or refreshes it.

    The receiver first consults the provided :class:`ThrottledTokenCache`.
    If the cached token is missing or too close to expiration (depending
    on the parent's ``safety_margin``), the receiver will fetch a fresh
    token from the wrapped bearer and persist it to the cache.

    :param bearer: The parent :class:`RenewableFileCacheBearer` containing
        configuration such as :attr:`safety_margin` and the wrapped bearer instance.
    :param cache: The throttled file-backed token cache.

    Behavior
    --------
    - When the cache holds a non-expired token and it is outside the
      safety margin, that token is returned immediately.
    - Otherwise a receiver from the wrapped bearer is used to fetch a
      fresh token. The new token is saved to the cache on success.
    """

    def __init__(
        self,
        bearer: "RenewableFileCacheBearer",
        cache: ThrottledTokenCache,
    ) -> None:
        """Create a renewable receiver.

        No file I/O occurs during construction; the cache performs lazy
        I/O when accessed.
        """
        super().__init__()
        self._bearer = bearer
        self._cache = cache
        self._receiver: ParentReceiver | None = None
        self._last_saved: Token | None = None
        self._from_cache: bool = True

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Return a cached token when valid or fetch and store a new one.

        :param timeout: Pass-through timeout to the wrapped receiver.
        :param options: Optional fetch options forwarded to the wrapped
            receiver.
        :returns: A valid :class:`Token` (possibly empty).
        """
        if self._from_cache:
            token = await self._cache.get()
        else:
            token = await self._cache.refresh()
            if self._last_saved == token:
                # Avoid reusing the same token after an error; treat as
                # missing so the wrapped receiver will be invoked.
                token = None

        if token is not None and not token.is_expired():
            if self._bearer.safety_margin is None or (
                not token.expiration
                or (
                    token.expiration - self._bearer.safety_margin
                    > datetime.now(timezone.utc)
                )
            ):
                self._from_cache = True
                self._last_saved = token
                return token

        # Cache miss or token too close to expiry: fetch from wrapped
        # bearer.
        self._from_cache = False
        log.debug("Fetching new token from bearer")
        if self._receiver is None:
            # The wrapped bearer must exist; leave the type-ignore where
            # the static checker cannot prove it.
            self._receiver = self._bearer.wrapped.receiver()  # type: ignore

        token = await self._receiver.fetch(timeout=timeout, options=options)
        if token.is_empty():
            self._last_saved = None
            return token
        await self._cache.set(token)
        self._last_saved = token
        return token

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Decide whether an error should be retried.

        - If the previous attempt read from cache, allow one retry so
          callers can fall back to the wrapped receiver.
        - If no wrapped receiver exists yet, permit retry so the first
          fetch attempt can create it.
        - Otherwise defer to the wrapped receiver's ``can_retry``.

        :param err: The exception that occurred.
        :param options: Optional receiver options forwarded to the wrapped
            receiver when applicable.
        :returns: Whether the operation should be retried.
        """
        if self._from_cache:
            self._from_cache = False
            return True

        if self._receiver is None:
            return True  # Retry if we don't have a receiver yet

        return self._receiver.can_retry(err, options)


class RenewableFileCacheBearer(ParentBearer):
    """Bearer that composes a wrapped bearer with a file-backed cache.

    :ivar safety_margin: A :class:`datetime.timedelta` or seconds value
        used to determine when a token is considered too close to expiry.
        If ``None``, the cache will be used until tokens are expired.

    :param bearer: Wrapped bearer used for refreshing tokens. Must be named.
    :param safety_margin: Safety margin before token expiration.
    :param cache_file: Path to the file used for persistent cache.
    :param throttle: In-memory throttle interval for cache reads.

    Example
    -------

    Wrap a custom bearer with a name and file cache::

        from nebius.sdk import SDK
        from nebius.aio.token.token import Bearer, Receiver, Token
        from nebius.aio.token.file_cache.renewable_bearer import (
            RenewableFileCacheBearer
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
        cached_bearer = RenewableFileCacheBearer(custom_bearer)

        sdk = SDK(credentials=cached_bearer)
    """

    def __init__(
        self,
        bearer: ParentBearer,
        safety_margin: timedelta | float = timedelta(hours=2),
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        throttle: timedelta | float = timedelta(minutes=5),
    ) -> None:
        """Create a renewable file-backed bearer.

        The constructor creates the underlying :class:`ThrottledTokenCache`.

        :raises ValueError: When the wrapped bearer has no name.
        """
        self._bearer = bearer
        if isinstance(safety_margin, (float, int)):
            safety_margin = timedelta(seconds=safety_margin)
        self.safety_margin: timedelta | None = safety_margin
        name = self._bearer.name
        if name is None:
            raise ValueError("Bearer must have a name for the cache.")
        self._cache = ThrottledTokenCache(
            name=name,
            cache_file=cache_file,
            throttle=throttle,
        )

    @property
    def wrapped(self) -> ParentBearer | None:
        """Return the wrapped bearer instance.

        :returns: The wrapped bearer passed at construction.
        """
        return self._bearer

    def receiver(self) -> ParentReceiver:
        """Return a :class:`RenewableFileCacheReceiver` bound to the cache.

        :returns: A receiver that uses the file cache and refreshes from
            the wrapped bearer when necessary.
        """
        return RenewableFileCacheReceiver(self, self._cache)
