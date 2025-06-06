from asyncio import sleep
from datetime import timedelta
from pathlib import Path
from time import time
from typing import IO, Any, AnyStr

from portalocker import Lock as PortalockerLock
from portalocker.constants import LockFlags
from portalocker.exceptions import AlreadyLocked
from portalocker.types import Mode


class Lock:
    def __init__(
        self,
        file_path: str | Path,
        mode: Mode = "a",
        shared: bool = False,
        timeout: timedelta | float | None = None,
        polling_interval: timedelta | float = timedelta(milliseconds=250),
        **fopen_kwargs: Any,
    ):
        self.file_path = Path(file_path)
        self.shared = shared
        self.timeout = (
            timeout.total_seconds() if isinstance(timeout, timedelta) else timeout
        )
        self.mode: Mode = mode
        self.fopen_kwargs = fopen_kwargs
        self.polling_interval = (
            polling_interval.total_seconds()
            if isinstance(polling_interval, timedelta)
            else polling_interval
        )
        lock_flags = LockFlags.SHARED if self.shared else LockFlags.EXCLUSIVE
        lock_flags |= LockFlags.NON_BLOCKING
        self.lock = PortalockerLock(
            self.file_path,
            mode=self.mode,
            timeout=0,
            flags=lock_flags,
            **self.fopen_kwargs,
        )

    async def __aenter__(self) -> IO[AnyStr]:
        start = time()
        while True:
            try:
                return self.lock.acquire()
            except AlreadyLocked:
                if self.timeout is not None and time() - start > self.timeout:
                    raise TimeoutError(
                        f"Failed to acquire lock on {self.file_path} after "
                        f"{self.timeout} seconds."
                    )
                await sleep(self.polling_interval)
                continue

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.lock.release()
