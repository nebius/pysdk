from abc import ABC, abstractmethod

from grpc.aio._metadata import Metadata


class Authenticator(ABC):
    @abstractmethod
    async def authenticate(
        self, metadata: Metadata, timeout: float | None = None
    ) -> None:
        raise NotImplementedError("Method not implemented!")

    @abstractmethod
    def can_retry(self, err: Exception) -> bool:
        return False


class Provider(ABC):
    @abstractmethod
    def authenticator(self) -> Authenticator:
        raise NotImplementedError("Method not implemented!")
