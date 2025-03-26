from abc import ABC, abstractmethod
from datetime import datetime, timezone


class Token:
    def __init__(self, token: str, expiration: datetime | None = None) -> None:
        self._tok = token
        if expiration is not None:
            self._exp = expiration
        else:
            expiration = datetime.now(timezone.utc)

    def __str__(self) -> str:
        return self._tok

    @property
    def token(self) -> str:
        return self._tok

    @property
    def expiration(self) -> datetime:
        return self._exp


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
