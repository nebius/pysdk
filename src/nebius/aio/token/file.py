"""File-backed static token bearer.

This module provides a tiny bearer implementation that reads a raw
access token from a filesystem path. It is useful for local testing,
scripting or environments where a short-lived token is written to a
file by an external process or host system.

The behaviour is intentionally simple: every fetch reads the token
file contents and returns a :class:`Token`. Empty file contents raise
an :class:`nebius.base.error.SDKError`.

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

from nebius.base.error import SDKError

from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

log = getLogger(__name__)


class Receiver(ParentReceiver):
    """A receiver that reads a token from a filesystem path.

    Each call to :meth:`_fetch` opens and reads the configured file, so
    the token may change between fetches if the file is updated by an
    external process.

    :param file: :class:`pathlib.Path` pointing to a file containing a
        raw access token (UTF-8 text). The file is read on each fetch
        and must contain a non-empty token string.
    """

    def __init__(self, file: Path) -> None:
        """Create a file-backed receiver."""
        super().__init__()
        self._file = file

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
        with open(self._file, "r") as f:
            token_value = f.read().strip()
        if token_value == "":
            raise SDKError("empty token file provided")
        tok = Token(token_value)
        log.debug(f"fetched token {tok} from file {self._file}")
        return tok

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Indicate that file-backed tokens are not retryable.

        The token is static from the perspective of this receiver; retries
        are not useful because there is no remote call to repeat.
        """
        return False


class Bearer(ParentBearer):
    """Bearer that provides file-backed :class:`Receiver` instances.

    The bearer accepts either a string path or a :class:`pathlib.Path`
    and expands the user's home directory. It does not validate the
    existence of the file at construction time.

    :param file: Filesystem path (string or :class:`pathlib.Path`) to
        the token file. Tilde expansion is performed.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from nebius.sdk import SDK
        from nebius.aio.token.file import Bearer

        sdk = SDK(credentials=Bearer("~/nebius.token"))
    """

    def __init__(self, file: str | Path) -> None:
        """Create a bearer for the given token file."""
        super().__init__()
        self._file = Path(file).expanduser()

    def receiver(self) -> Receiver:
        """Return a :class:`Receiver` that reads tokens from the file.

        :returns: A new :class:`Receiver` bound to the configured file.
        """
        return Receiver(self._file)
