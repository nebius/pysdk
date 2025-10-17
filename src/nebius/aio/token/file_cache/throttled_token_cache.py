"""Throttled token cache helper.

This module provides :class:`ThrottledTokenCache`, a thin wrapper around
:class:`TokenCache` which prevents frequent disk reads by caching the
value in-memory for a configurable throttle period.

The class is useful when many coroutines may request the same token
frequently and you want to reduce filesystem and YAML parsing overhead.

Example
-------

    cache = ThrottledTokenCache("service-account")
    tok = await cache.get()

"""

from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path

from nebius.aio.token.token import Token
from nebius.base.constants import DEFAULT_CONFIG_DIR, DEFAULT_CREDENTIALS_FILE

from .token_cache import TokenCache

log = getLogger(__name__)


class ThrottledTokenCache:
    """A throttled file-based token cache.

    The helper keeps an in-memory cached token for ``throttle`` seconds
    to avoid repeated reads from the underlying :class:`TokenCache`.

    :param name: The key name under which the token is stored in the
        underlying :class:`TokenCache`.
    :param cache_file: Path to the underlying YAML cache file.
    :param throttle: Duration (timedelta or seconds as float) to
        hold the in-memory cached token. If a float is supplied it is
        interpreted as seconds.
    """

    def __init__(
        self,
        name: str,
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        throttle: timedelta | float = timedelta(minutes=5),
    ) -> None:
        """Create a throttled token cache."""
        self._name = name
        self._cache = TokenCache(cache_file)
        if isinstance(throttle, (float, int)):
            throttle = timedelta(seconds=throttle)
        self._throttle: timedelta = throttle
        self._cached_token: Token | None = None
        self._next_check: datetime = datetime.now(timezone.utc)

    def get_cached(self) -> Token | None:
        """Return the in-memory cached token without consulting disk.

        :returns: The cached :class:`Token` or `None` if no token is cached.
        """
        return self._cached_token

    async def get(self) -> Token | None:
        """Return the cached token, refreshing from disk if throttling allows.

        If the in-memory token is present, not expired and the throttle
        period has not elapsed the cached token is returned. Otherwise
        the underlying :meth:`TokenCache.get` is called.

        :returns: The cached :class:`Token` or `None` if no valid token is found.
        """
        if (
            self._cached_token is not None
            and not self._cached_token.is_expired()
            and self._next_check > datetime.now(timezone.utc)
        ):
            return self._cached_token

        return await self.refresh()

    async def set(self, token: Token) -> None:
        """Store the token in the underlying cache and update the in-memory
        cache and throttle expiration.

        If the provided token equals the in-memory cached token no write is performed.
        """
        if self._cached_token == token:
            return
        await self._cache.set(self._name, token)
        self._cached_token = token
        self._next_check = datetime.now(timezone.utc) + self._throttle

    async def remove(self) -> None:
        """Remove the token from both the underlying cache and the in-memory cache."""
        await self._cache.remove(self._name)
        self._cached_token = None
        self._next_check = datetime.now(timezone.utc)

    async def remove_if_equal(self, token: Token) -> None:
        """Remove the token if it equals the provided token.

        This performs an atomic check-and-remove against the underlying
        cache and updates the in-memory state when the removal occurs.
        """
        await self._cache.remove_if_equal(self._name, token)
        if self._cached_token == token:
            self._cached_token = None
            self._next_check = datetime.now(timezone.utc)

    async def refresh(self) -> Token | None:
        """Refresh the in-memory token from the underlying cache.

        If the token exists on disk and is not expired the in-memory
        cache and throttle are updated and the token is returned.
        """
        token = await self._cache.get(self._name)
        if token is not None and not token.is_expired():
            self._cached_token = token
            self._next_check = datetime.now(timezone.utc) + self._throttle
            return token
        return None
