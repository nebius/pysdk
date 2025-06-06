from datetime import datetime, timedelta, timezone
from logging import getLogger
from pathlib import Path

from nebius.aio.token.token import Token
from nebius.base.constants import DEFAULT_CONFIG_DIR, DEFAULT_CREDENTIALS_FILE

from .token_cache import TokenCache

log = getLogger(__name__)


class ThrottledTokenCache:
    """
    A throttled file-based token cache.
    """

    def __init__(
        self,
        name: str,
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        throttle: timedelta | float = timedelta(minutes=5),
    ) -> None:
        self._name = name
        self._cache = TokenCache(cache_file)
        if isinstance(throttle, (float, int)):
            throttle = timedelta(seconds=throttle)
        self._throttle: timedelta = throttle
        self._cached_token: Token | None = None
        self._next_check: datetime = datetime.now(timezone.utc)

    def get_cached(self) -> Token | None:
        """
        Get the cached token without checking the throttle.
        """
        return self._cached_token

    async def get(self) -> Token | None:
        """
        Get the cached token, respecting the throttle.
        """
        if (
            self._cached_token is not None
            and not self._cached_token.is_expired()
            and self._next_check > datetime.now(timezone.utc)
        ):
            return self._cached_token

        return await self.refresh()

    async def set(self, token: Token) -> None:
        """
        Set the token in the cache and update the throttle.
        """
        if self._cached_token == token:
            return
        await self._cache.set(self._name, token)
        self._cached_token = token
        self._next_check = datetime.now(timezone.utc) + self._throttle

    async def remove(self) -> None:
        """
        Remove the token from the cache.
        """
        await self._cache.remove(self._name)
        self._cached_token = None
        self._next_check = datetime.now(timezone.utc)

    async def remove_if_equal(self, token: Token) -> None:
        """
        Remove the token from the cache if it matches the provided token.
        """
        await self._cache.remove_if_equal(self._name, token)
        if self._cached_token == token:
            self._cached_token = None
            self._next_check = datetime.now(timezone.utc)

    async def refresh(self) -> Token | None:
        """
        Refresh the cached token by fetching it again.
        """
        token = await self._cache.get(self._name)
        if token is not None and not token.is_expired():
            self._cached_token = token
            self._next_check = datetime.now(timezone.utc) + self._throttle
            return token
        return None
