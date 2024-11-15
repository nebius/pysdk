from grpc.aio._metadata import Metadata

from ..token import token
from .authorization import Authenticator, Provider

HEADER = "authorization"


class TokenAuthenticator(Authenticator):
    def __init__(self, receiver: token.Receiver) -> None:
        super().__init__()
        self._receiver = receiver

    async def authenticate(
        self, metadata: Metadata, timeout: float | None = None
    ) -> None:
        tok = await self._receiver.fetch(timeout=timeout)
        metadata.add(HEADER, f"Bearer {tok}")

    def can_retry(self, err: Exception) -> bool:
        return self._receiver.can_retry(err)


class TokenProvider(Provider):
    def __init__(self, token_provider: token.Bearer) -> None:
        super().__init__()
        self._provider = token_provider

    def authenticator(self) -> Authenticator:
        return TokenAuthenticator(self._provider.receiver())
