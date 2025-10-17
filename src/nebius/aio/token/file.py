from logging import getLogger
from pathlib import Path

from nebius.base.error import SDKError

from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

log = getLogger(__name__)


class NoTokenInEnvError(SDKError):
    pass


class Receiver(ParentReceiver):
    def __init__(self, file: Path) -> None:
        super().__init__()
        self._file = file

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
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
        return False


class Bearer(ParentBearer):
    def __init__(self, file: str | Path) -> None:
        super().__init__()
        self._file = Path(file).expanduser()

    def receiver(self) -> Receiver:
        return Receiver(self._file)
