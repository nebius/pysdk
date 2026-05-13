"""File-backed static token bearer.

This module provides a tiny bearer implementation that reads a raw
access token from a filesystem path. It is useful for local testing,
scripting or environments where a short-lived token is written to a
file by an external process or host system.

Fetched tokens are cached for a short refresh period to avoid reading
the file for every request. If a request fails with an authentication
error, :meth:`Receiver.can_retry` checks whether the file now contains a
different token and invalidates the cache so the retry re-reads the file.
Empty file contents raise an :class:`nebius.base.error.SDKError`.

Examples
--------

Create a bearer that reads from ``~/.nebius/token``::

    from nebius.aio.token.file import Bearer
    bearer = Bearer("~/.nebius/token")
    token = await bearer.receiver().fetch()

Use in code that expects a :class:`nebius.aio.token.token.Bearer`::

    sdk = SDK(credentials=bearer)

"""

from logging import getLogger
from pathlib import Path
from time import monotonic

from nebius.aio.metrics import (
    METRIC_RESULT_ERROR,
    METRIC_RESULT_SUCCESS,
    AuthMetricsLike,
    auth_metrics_recorder,
    metric_start,
)
from nebius.base.error import SDKError

from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

log = getLogger(__name__)


class Receiver(ParentReceiver):
    """A receiver that reads a token from a filesystem path.

    Calls to :meth:`_fetch` return the bearer's cached token when it is
    still fresh; otherwise the configured file is opened and read. When
    authentication fails, :meth:`can_retry` invalidates the cache and
    retries only if the token file changed.

    :param file: :class:`pathlib.Path` pointing to a file containing a
        raw access token (UTF-8 text). The file is read on each fetch
        and must contain a non-empty token string.
    """

    def __init__(self, bearer: "Bearer") -> None:
        """Create a file-backed receiver."""
        super().__init__()
        self._bearer = bearer

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Read the token file and return a :class:`Token`.

        :param timeout: Ignored for file-backed receivers but accepted for
            API compatibility.
        :param options: Ignored; present for API compatibility.
        :returns: A :class:`Token` constructed from the file contents.
        :raises SDKError: If the file contains an empty string.
        :raises OSError: If the file cannot be opened.
        """
        return self._bearer.fetch_token()

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Retry only when the token file changed after the last fetch.

        Authentication failures may be caused by an external process rotating
        the token file. The bearer clears its cache and compares current file
        contents with the token used by this receiver. If they differ, the
        request layer may authenticate again and pick up the new token.
        """
        latest = self.latest
        if latest is None or latest.is_empty():
            return False
        return self._bearer.should_retry_after_error(latest)


class Bearer(ParentBearer):
    """Bearer that provides file-backed :class:`Receiver` instances.

    The bearer accepts either a string path or a :class:`pathlib.Path`
    and expands the user's home directory. It does not validate the
    existence of the file at construction time. Tokens are cached for
    ``refresh_period`` seconds; pass ``0`` to keep a successfully-read token
    cached until an authentication failure invalidates it.

    :param file: Filesystem path (string or :class:`pathlib.Path`) to
        the token file. Tilde expansion is performed.
    :param refresh_period: Cache freshness window in seconds. Defaults to
        five minutes.
    :param metrics: Optional auth metrics callbacks used to record file reads,
        cache hits, cache misses, and invalidations.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from nebius.sdk import SDK
        from nebius.aio.token.file import Bearer

        sdk = SDK(credentials=Bearer("~/nebius.token"))
    """

    def __init__(
        self,
        file: str | Path,
        refresh_period: float = 5 * 60,
        metrics: AuthMetricsLike = None,
    ) -> None:
        """Create a bearer for the given token file."""
        super().__init__()
        self._file = Path(file).expanduser()
        self._refresh_period = refresh_period
        self._metrics = auth_metrics_recorder(
            metrics,
            "file",
        )
        self._cached_token: Token | None = None
        self._refresh_at = 0.0

    def receiver(self) -> Receiver:
        """Return a :class:`Receiver` that reads tokens from the file.

        :returns: A new :class:`Receiver` bound to the configured file.
        """
        return Receiver(self)

    def fetch_token(self) -> Token:
        """Return a cached file token or read and cache it from disk."""

        now = monotonic()
        if (
            self._cached_token is not None
            and not self._cached_token.is_empty()
            and (self._refresh_period == 0 or now < self._refresh_at)
        ):
            self._metrics.cache_hit()
            return self._cached_token

        start = metric_start()
        try:
            token_value = self._read_token_value()
            tok = Token(token_value)
            self._cached_token = tok
            self._refresh_at = monotonic() + self._refresh_period
            self._metrics.token_acquire_from_start(METRIC_RESULT_SUCCESS, start, 0, tok)
            self._metrics.cache_miss(METRIC_RESULT_SUCCESS)
            log.debug(f"fetched token {tok} from file {self._file}")
            return tok
        except Exception:
            self._metrics.token_acquire_from_start(METRIC_RESULT_ERROR, start, 0)
            self._metrics.cache_miss(METRIC_RESULT_ERROR)
            raise

    def should_retry_after_error(self, token: Token) -> bool:
        """Invalidate cached token and return whether the file token changed."""

        if (
            self._cached_token is not None
            and not self._cached_token.is_empty()
            and self._cached_token.token != token.token
        ):
            self._invalidate_cache()
            return True

        self._invalidate_cache()
        try:
            token_value = self._read_token_value()
        except Exception:
            return False
        return token_value != token.token

    def set_metrics(self, metrics: AuthMetricsLike) -> None:
        """Attach auth metrics callbacks used by subsequently created receivers."""

        self._metrics.set_metrics(metrics)

    def _read_token_value(self) -> str:
        token_value = self._file.read_text().strip()
        if token_value == "":
            raise SDKError("empty token file provided")
        if "\n" in token_value:
            raise SDKError(f"invalid token file: {self._file} contains newline")
        return token_value

    def _invalidate_cache(self) -> None:
        if self._cached_token is not None:
            self._metrics.cache_invalidate()
        self._cached_token = None
        self._refresh_at = 0.0
