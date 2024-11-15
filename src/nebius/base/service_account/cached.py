from logging import getLogger
from threading import Lock

from .service_account import Reader as BaseReader
from .service_account import ServiceAccount

log = getLogger(__name__)


class Reader(BaseReader):
    def __init__(self, next: BaseReader) -> None:
        self._next = next
        self._cache: ServiceAccount | None = None
        self._lock = Lock()

    def read(self) -> ServiceAccount:
        log.debug("reading cached SA")
        with self._lock:
            if self._cache is None:
                log.debug("cache is empty, reading SA into cache")
                self._cache = self._next.read()
        return self._cache
