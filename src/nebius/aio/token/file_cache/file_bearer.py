from datetime import timedelta
from logging import getLogger
from pathlib import Path

from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import Receiver as ParentReceiver
from nebius.aio.token.token import Token
from nebius.base.constants import DEFAULT_CONFIG_DIR, DEFAULT_CREDENTIALS_FILE

from .throttled_token_cache import ThrottledTokenCache

log = getLogger(__name__)


class PureFileCacheReceiver(ParentReceiver):
    def __init__(self, cache: ThrottledTokenCache) -> None:
        super().__init__()
        self._cache = cache

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        return await self._cache.get() or Token.empty()

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        return False


class PureFileCacheBearer(ParentBearer):
    def __init__(
        self,
        name: str,
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        throttle: timedelta | float = timedelta(minutes=5),
    ) -> None:
        self._name = name
        self._cache = ThrottledTokenCache(
            name=self._name, cache_file=cache_file, throttle=throttle
        )

    @property
    def name(self) -> str:
        return self._name

    def receiver(self) -> ParentReceiver:
        return PureFileCacheReceiver(self._cache)
