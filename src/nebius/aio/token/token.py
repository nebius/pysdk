from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from nebius.base.token_sanitizer import TokenSanitizer

sanitizer = TokenSanitizer.access_token_sanitizer()


class Token:
    def __init__(self, token: str, expiration: datetime | None = None) -> None:
        self._tok = token
        self._exp = expiration

    def __str__(self) -> str:
        if self.is_empty():
            return "Token(empty)"
        ret = ["Token("]
        ret.append(sanitizer.sanitize(self._tok))
        if self._exp is not None:
            ret.append(f", expiration={self._exp.isoformat()}")
            expires_in = self._exp - datetime.now(timezone.utc)
            ret.append(f", expires_in={expires_in}")
        else:
            ret.append(", expiration=None")
        ret.append(")")
        return "".join(ret)

    @classmethod
    def empty(cls) -> "Token":
        """
        Create an empty token.
        """
        return cls(token="")

    @property
    def token(self) -> str:
        return self._tok

    @property
    def expiration(self) -> datetime | None:
        return self._exp

    def is_empty(self) -> bool:
        return self._tok == ""

    def is_expired(self) -> bool:
        if self._exp is None:
            return False
        return datetime.now(timezone.utc) >= self._exp

    def to_dict(self) -> dict[str, Any]:
        expires_at = int(self._exp.timestamp()) if self._exp is not None else 0
        data: dict[str, Any] = {
            "token": self._tok,
            "expires_at": expires_at if self._exp is not None else None,
        }
        return data

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Token):
            return NotImplemented
        return self._tok == value._tok and self._exp == value._exp

    @classmethod
    def from_dict(cls, data: Any) -> "Token":
        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid format for Token: {type(data)} expected a dictionary.",
            )
        token = data.get("token", "")  # type: ignore[assignment,unused-ignore]
        if token is None:
            token = ""
        if not isinstance(token, str):
            raise ValueError(f"Invalid token format: {type(token)} expected a string.")  # type: ignore[assignment,unused-ignore]
        expires_at = data.get("expires_at", None)  # type: ignore[assignment,unused-ignore]
        if expires_at is None:
            return cls(token=token)
        if not isinstance(expires_at, int):
            raise ValueError(
                f"Invalid expires_at format: {type(expires_at)} expected an int."  # type: ignore[assignment,unused-ignore]
            )
        expiration = (
            datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None
        )
        return cls(token=token, expiration=expiration)


class Receiver(ABC):
    _latest: Token | None

    @abstractmethod
    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        raise NotImplementedError("Method not implemented!")

    @property
    def latest(self) -> Token | None:
        return self._latest

    async def fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        tok = await self._fetch(timeout=timeout, options=options)
        self._latest = tok
        return tok

    @abstractmethod
    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        return False


class Bearer(ABC):
    @abstractmethod
    def receiver(self) -> Receiver:
        raise NotImplementedError("Method not implemented!")

    @property
    def name(self) -> str | None:
        if self.wrapped is not None:
            return self.wrapped.name
        return None

    @property
    def wrapped(self) -> "Bearer|None":
        return None

    async def close(self, grace: float | None = None) -> None:
        if self.wrapped is not None:
            await self.wrapped.close(grace=grace)
        return None


class NamedBearer(Bearer):
    def __init__(self, wrapped: Bearer, name: str) -> None:
        self._wrapped = wrapped
        self._name = name

    @property
    def wrapped(self) -> Bearer:
        return self._wrapped

    @property
    def name(self) -> str | None:
        return self._name

    def receiver(self) -> Receiver:
        return self._wrapped.receiver()
