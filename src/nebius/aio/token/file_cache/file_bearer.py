"""File-backed bearer helpers.

This module adapts :class:`ThrottledTokenCache` into the Bearer/Receiver
abstractions used by the SDK. It provides lightweight types intended for
simple file-backed credential lookups.

Types
-----

- :class:`PureFileCacheReceiver` -- A :class:`nebius.aio.token.token.Receiver`
    implementation that reads a token from a :class:`ThrottledTokenCache`.
    It does not perform retries; the cache layer implements throttling and
    robustness.
- :class:`PureFileCacheBearer` -- A :class:`nebius.aio.token.token.Bearer` that
    constructs a :class:`ThrottledTokenCache` for a named credential and
    returns a :class:`PureFileCacheReceiver` when requested.

Example
-------

Create a bearer that reads credentials from the default credentials file
and caches them for five minutes::

    from nebius.aio.token.file_cache.file_bearer import PureFileCacheBearer
    from nebius.sdk import SDK

    bearer = PureFileCacheBearer('my-service')
    sdk = SDK(credentials=bearer)

"""

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
    """Receiver that reads tokens from a :class:`ThrottledTokenCache`.

    Behavior
    --------
    - ``_fetch`` returns the token stored in the cache or
      :meth:`nebius.aio.token.token.Token.empty` when no token exists.
    - ``can_retry`` returns ``False``; callers should not apply transport
      retries to a local file cache.

    :param cache: Throttled token cache implementation.
    """

    def __init__(self, cache: ThrottledTokenCache) -> None:
        """Create a receiver backed by ``cache``.

        No file I/O occurs during construction; the cache performs I/O on demand.
        """
        super().__init__()
        self._cache = cache

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Return the cached token or an empty token.

        :param timeout: Ignored. Present for interface compatibility.
        :param options: Unused by this receiver.
        :returns: Token from the underlying cache or an empty token.

        """
        return await self._cache.get() or Token.empty()

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Return `False` to indicate no retries should be attempted.

        :param err: The exception raised during a prior fetch attempt.
        :param options: Optional receiver options (unused).
        :returns: Always `False`.
        """
        return False


class PureFileCacheBearer(ParentBearer):
    """Bearer that exposes a :class:`PureFileCacheReceiver` for a named
    token.

    Notes
    -----

    Construction is inexpensive; the cache performs I/O lazily when
    tokens are accessed via the receiver.

    :param name: Logical name for the credential.
    :param cache_file: Destination YAML file used to persist tokens.
    :param throttle: Throttle interval for in-memory caching.

    Example
    -------

    Create a bearer that reads credentials from the default credentials file
    and caches them for five minutes::

        from nebius.aio.token.file_cache.file_bearer import PureFileCacheBearer
        from nebius.sdk import SDK

        bearer = PureFileCacheBearer('my-service')
        sdk = SDK(credentials=bearer)
    """

    def __init__(
        self,
        name: str,
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        throttle: timedelta | float = timedelta(minutes=5),
    ) -> None:
        """Create a bearer backed by a throttled file cache."""
        self._name = name
        self._cache = ThrottledTokenCache(
            name=self._name, cache_file=cache_file, throttle=throttle
        )

    @property
    def name(self) -> str:
        """Return the logical name for this bearer.

        :returns: The name provided at construction.
        """
        return self._name

    def receiver(self) -> ParentReceiver:
        """Return a :class:`PureFileCacheReceiver` bound to the cache.

        Each call returns a fresh receiver that references the same
        :class:`ThrottledTokenCache` instance.

        :returns: A receiver that reads from the shared cache.
        """
        return PureFileCacheReceiver(self._cache)
