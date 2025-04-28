from logging import getLogger
from os.path import expanduser

from nebius.base.error import SDKError

from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

log = getLogger(__name__)


class NoTokenInEnvError(SDKError):
    pass


class Receiver(ParentReceiver):
    def __init__(self, token: Token) -> None:
        super().__init__()
        self._latest = token

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        if self._latest is None:
            raise Exception("Token has to be set")
        log.debug("static token fetched")
        return self._latest

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        return False


class Bearer(ParentBearer):
    def __init__(self, file: str) -> None:
        super().__init__()
        with open(expanduser(file), "r") as f:
            token_value = f.read().strip()
        if token_value == "":
            raise SDKError("empty token file provided")
        self._tok = Token(token_value)

    def receiver(self) -> Receiver:
        return Receiver(self._tok)
