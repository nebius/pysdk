"""File-based token cache used by the SDK.

This module provides :class:`TokenCache`, a small asynchronous file
cache that stores named :class:`nebius.aio.token.token.Token` objects in
a YAML file. Access to the cache is protected by a file lock
(:class:`nebius.aio.token.file_cache.async_flock.Lock`) to ensure
concurrent processes or coroutines do not corrupt the cache.

The cache stores data in YAML under the ``tokens`` key where each
token value is the mapping produced by :meth:`Token.to_dict` and may
include an ``expires_at`` timestamp. Expired tokens are ignored and
cleaned up automatically.

Example
-------

    cache = TokenCache()
    await cache.set("my-token", Token("abc", expiration=...))
    tok = await cache.get("my-token")
"""

from logging import getLogger
from pathlib import Path

import yaml

from nebius.aio.token.token import Token
from nebius.base.constants import DEFAULT_CONFIG_DIR, DEFAULT_CREDENTIALS_FILE

from .async_flock import Lock

log = getLogger(__name__)


class TokenCache:
    """A simple asynchronous file-based token cache.

    The cache stores named tokens in a YAML document on disk and uses a
    file lock to serialize concurrent access. Tokens are automatically
    filtered for expiration when reading and writing.

    :ivar cache_file: Path to the YAML cache file.
    :ivar path_create_mode: Mode used when creating parent directories.
    :ivar file_create_mode: Mode used when creating the cache file.
    :ivar flock_timeout: Timeout in seconds to wait for the file lock. `None`
        means wait indefinitely.

    :param cache_file: Filesystem path to the YAML cache file. When a
        string is supplied it is expanded with :meth:`pathlib.Path.expanduser`.
    :type cache_file: `str` or :class:`pathlib.Path`
    :param path_create_mode: Mode used when creating parent directories
        (default 0o750).
    :param file_create_mode: Mode used when creating the cache file
        (default 0o600).
    :param flock_timeout: Timeout in seconds to wait for the file lock
        when accessing the cache. ``None`` means wait indefinitely.
    """

    def __init__(
        self,
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        path_create_mode: int = 0o750,
        file_create_mode: int = 0o600,
        flock_timeout: float | None = 5.0,
    ) -> None:
        """Create or reference a token cache file."""
        self.cache_file = Path(cache_file).expanduser()
        self.flock_timeout = flock_timeout
        self.file_create_mode = file_create_mode
        self.path_create_mode = path_create_mode

    def _yaml_parse(self, data: str) -> dict[str, Token]:
        """Parse YAML content and return a mapping of token name -> Token.

        The function expects a YAML mapping with a top-level ``tokens`` key
        containing a mapping of string names to token dictionaries produced
        by :meth:`Token.to_dict`.

        :param data: YAML document as a string.
        :returns: Mapping from token name to :class:`Token`.
        :raises ValueError: When the YAML is invalid or has an unexpected
            structure.
        """
        try:
            data = yaml.safe_load(data) or {}  # type: ignore
            if not isinstance(data, dict):
                raise ValueError(
                    f"Invalid YAML format: {type(data)} expected a dictionary."
                )
            tokens_strs = data.get("tokens", {})  # type: ignore[unused-ignore]
            if not isinstance(tokens_strs, dict):
                raise ValueError(
                    f"Invalid tokens format: {type(tokens_strs)} expected a dictionary."  # type: ignore[unused-ignore]
                )
            tokens = dict[str, Token]()
            for k, v in tokens_strs.items():  # type: ignore[unused-ignore]
                if not isinstance(k, str):
                    raise ValueError(
                        f"Invalid token format: key '{k}' must be a string."
                    )

                tokens[k] = Token.from_dict(v)
            return tokens
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML data: {e}")

    async def get(self, name: str) -> Token | None:
        """Return the token with the given name or `None`.

        The function opens the cache file under a shared/read lock and
        parses the YAML content. If the token is present and not expired
        it is returned. Expired tokens are removed from the cache.

        :param name: Token name to lookup.
        :returns: :class:`Token` instance or `None` when not found or expired.
        """
        try:
            if not self.cache_file.is_file():
                return None
            async with Lock(
                self.cache_file,
                "r",
                create_mode=self.file_create_mode,
                timeout=self.flock_timeout,
            ) as f:  # type: ignore[unused-ignore]
                tokens = self._yaml_parse(f.read())  # type: ignore[unused-ignore]
            ret = tokens.get(name, None)
            if ret is not None and not ret.is_expired():
                return ret
            await self.remove(name)  # Clean up expired token
            return None
        except ValueError as e:
            log.warning(
                f"Failed to parse tokens from {self.cache_file}. "
                f"Returning None for the requested token: {e}"
            )
            return None
        except FileNotFoundError:
            return None

    def _yaml_dump(self, tokens: dict[str, Token]) -> str:
        """Serialize tokens to a YAML document.

        Expired tokens are omitted from the serialized output.

        :param tokens: Mapping of token name to :class:`Token`.
        :returns: YAML string or an empty string when there are no tokens to persist.
        """
        toks = {k: v.to_dict() for k, v in tokens.items() if not v.is_expired()}
        if len(toks) == 0:
            return ""
        return yaml.dump(
            {"tokens": toks},
            sort_keys=False,
        )

    async def set(self, name: str, token: Token) -> None:
        """Store a token in the cache under the given name.

        The cache file and its parent directory are created with the
        configured permissions if necessary. The function acquires an
        exclusive lock while reading and writing the YAML document.

        :param name: Name under which to store the token.
        :param token: :class:`Token` instance to store.
        :raises ValueError: If the token cannot be serialized or written.
        """
        try:
            if not self.cache_file.parent.is_dir():
                self.cache_file.parent.mkdir(
                    mode=self.path_create_mode, parents=True, exist_ok=True
                )
            async with Lock(
                self.cache_file,
                "a+",
                create_mode=self.file_create_mode,
                timeout=self.flock_timeout,
            ) as f:  # type: ignore[unused-ignore]
                f.seek(0)
                try:
                    tokens = self._yaml_parse(f.read())  # type: ignore[unused-ignore]
                except ValueError as e:
                    log.warning(
                        f"Failed to parse tokens from {self.cache_file}. "
                        f"Starting with an empty cache: {e}"
                    )
                    tokens = {}
                tokens[name] = token
                f.seek(0)
                f.truncate()
                f.write(self._yaml_dump(tokens))  # type: ignore[unused-ignore]
        except ValueError as e:
            raise ValueError(f"Failed to set token: {e}")

    async def remove(self, name: str) -> None:
        """Remove the token with the specified name from the cache.

        The function opens the cache under an exclusive lock, removes the
        entry when present and writes the updated YAML document back to disk.

        :param name: Token name to remove.
        :raises ValueError: If the cache cannot be parsed or written.
        """
        try:
            if not self.cache_file.is_file():
                return
            async with Lock(
                self.cache_file,
                "r+",
                create_mode=self.file_create_mode,
                timeout=self.flock_timeout,
            ) as f:  # type: ignore[unused-ignore]
                try:
                    tokens = self._yaml_parse(f.read())  # type: ignore[unused-ignore]
                except ValueError as e:
                    log.warning(
                        f"Failed to parse tokens from {self.cache_file}. "
                        f"Starting with an empty cache: {e}"
                    )
                    tokens = {}
                if name in tokens:
                    del tokens[name]
                f.seek(0)
                f.truncate()
                f.write(self._yaml_dump(tokens))  # type: ignore[unused-ignore]
        except ValueError as e:
            raise ValueError(f"Failed to remove token: {e}")

    async def remove_if_equal(self, name: str, token: Token) -> None:
        """Remove the token only if its value equals the provided token.

        The comparison uses :meth:`Token.__eq__`.

        :param name: Token name to remove.
        :param token: Token value to compare against.
        :raises ValueError: If the cache cannot be parsed or written.
        """
        try:
            if not self.cache_file.is_file():
                return
            async with Lock(
                self.cache_file,
                "r+",
                create_mode=self.file_create_mode,
                timeout=self.flock_timeout,
            ) as f:  # type: ignore[unused-ignore]
                try:
                    tokens = self._yaml_parse(f.read())  # type: ignore[unused-ignore]
                except ValueError as e:
                    log.warning(
                        f"Failed to parse tokens from {self.cache_file}. "
                        f"Starting with an empty cache: {e}"
                    )
                    tokens = {}
                if name in tokens and tokens[name] == token:
                    del tokens[name]
                f.seek(0)
                f.truncate()
                f.write(self._yaml_dump(tokens))  # type: ignore[unused-ignore]
        except ValueError as e:
            raise ValueError(f"Failed to remove token: {e}")
