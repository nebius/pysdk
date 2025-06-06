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
    def __init__(
        self,
        bearer: "RenewableFileCacheBearer",
        cache: ThrottledTokenCache,
    ) -> None:
        super().__init__()
        self._bearer = bearer
        self._cache = cache
        self._receiver: ParentReceiver | None = None
        self._last_saved: Token | None = None
        self._from_cache: bool = True

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        if self._from_cache:
            token = await self._cache.get()
        else:
            token = await self._cache.refresh()
            if self._last_saved == token:
                token = None  # to avoid using the same token if error occurs
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

        self._from_cache = False
        log.debug("Fetching new token from bearer")
        if self._receiver is None:
            self._receiver = self._bearer.wrapped.receiver()  # type: ignore  # can't be None

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
        if self._from_cache:
            self._from_cache = False
            return True

        if self._receiver is None:
            return True  # Retry if we don't have a receiver yet

        return self._receiver.can_retry(err, options)


class RenewableFileCacheBearer(ParentBearer):
    def __init__(
        self,
        bearer: ParentBearer,
        safety_margin: timedelta | float = timedelta(hours=2),
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        throttle: timedelta | float = timedelta(minutes=5),
    ) -> None:
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
        return self._bearer

    def receiver(self) -> ParentReceiver:
        return RenewableFileCacheReceiver(self, self._cache)
