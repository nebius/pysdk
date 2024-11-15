from logging import getLogger

from .service_account import Reader as BaseReader
from .service_account import ServiceAccount

log = getLogger(__name__)


class Reader(BaseReader):
    def __init__(self, service_account: ServiceAccount) -> None:
        self._sa = service_account

    def read(self) -> ServiceAccount:
        log.debug("static SA read")
        return self._sa
