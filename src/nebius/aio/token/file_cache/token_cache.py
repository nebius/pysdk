from logging import getLogger
from pathlib import Path

import yaml

from nebius.aio.token.token import Token
from nebius.base.constants import DEFAULT_CONFIG_DIR, DEFAULT_CREDENTIALS_FILE

from .async_flock import Lock

log = getLogger(__name__)


class TokenCache:
    """
    A simple file-based token cache.
    """

    def __init__(
        self,
        cache_file: str | Path = Path(DEFAULT_CONFIG_DIR) / DEFAULT_CREDENTIALS_FILE,
        path_create_mode: int = 0o750,
        file_create_mode: int = 0o600,
        flock_timeout: float | None = 5.0,
    ) -> None:
        self.cache_file = Path(cache_file).expanduser()
        self.flock_timeout = flock_timeout
        self.file_create_mode = file_create_mode
        self.path_create_mode = path_create_mode

    def _yaml_parse(self, data: str) -> dict[str, Token]:
        """
        Parse YAML data from a string.
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
        """
        Get a token from the cache by name.
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
        """
        Dump tokens to a YAML string.
        """
        toks = {k: v.to_dict() for k, v in tokens.items() if not v.is_expired()}
        if len(toks) == 0:
            return ""
        return yaml.dump(
            {"tokens": toks},
            sort_keys=False,
        )

    async def set(self, name: str, token: Token) -> None:
        """
        Set a token in the cache by name.
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
        """
        Remove a token from the cache by name.
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
        """
        Remove a token from the cache by name if it matches the provided token.
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
