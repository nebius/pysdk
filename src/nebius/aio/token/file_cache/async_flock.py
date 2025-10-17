"""Asynchronous file lock using portalocker.

This module provides a small ``async``-compatible file lock wrapper
around :mod:`portalocker`. It exposes :class:`Lock` which can be used
with ``async with`` to acquire a file-based lock without blocking the
event loop (the implementation performs polling with ``asyncio.sleep``).

The lock supports exclusive and shared modes and a configurable
timeout/polling interval.

Examples
--------

Acquire an exclusive lock::

    async with Lock("/var/lock/my.lock"):
        # protected critical section
        do_stuff()

Acquire a shared lock with a short timeout::

    async with Lock("/var/lock/my.lock", shared=True, timeout=0.5):
        read_shared_resource()

"""

from asyncio import sleep
from datetime import timedelta
from pathlib import Path
from time import time
from typing import IO, Any, AnyStr

from portalocker import Lock as PortalockerLock
from portalocker.constants import LockFlags
from portalocker.exceptions import AlreadyLocked


class Lock:
    """Asynchronous context manager performing a file lock.

    The :class:`Lock` class implements the asynchronous context manager
    protocol (:meth:`__aenter__`/:meth:`__aexit__`) and uses :mod:`portalocker` to
    create a platform-native file lock. The implementation is non-blocking
    for the event loop because it polls to acquire the lock using
    :func:`asyncio.sleep` between attempts.

    Example
    -------

    ::

        async with Lock("/tmp/my.lock", timeout=2.0):
            # critical section
            await do_something()

    :ivar file_path: Path to the lock file.
    :ivar shared: If `True`, acquire a shared (read) lock; otherwise
        acquire an exclusive (write) lock.
    :ivar create_mode: File mode used when creating the lock file.
    :ivar timeout: Maximum time in seconds to wait for the lock. If `None`, wait
        indefinitely.
    :ivar polling_interval: Time in seconds between lock acquisition attempts,
        defaults to 0.25 seconds.
    :ivar lock: Underlying :class:`portalocker.Lock` instance.
    :ivar mode: File open mode passed to portalocker.
    :ivar fopen_kwargs: Additional keyword arguments passed to the
        underlying :func:`open` call used by portalocker.

    :param file_path: Path to the lock file.
    :param mode: File open mode passed to portalocker (default: "a").
    :param create_mode: File mode used when creating the lock file
        (default: 0o644). Ignored if the file already exists.
    :param shared: If `True`, acquire a shared (read) lock; otherwise
        acquire an exclusive (write) lock.
    :param timeout: Maximum time in seconds to wait for the lock. If `None`,
        wait indefinitely.
    :param polling_interval: Time in seconds between lock acquisition attempts,
        defaults to 0.25 seconds.
    :param fopen_kwargs: Additional keyword arguments passed to the
        underlying :func:`open` call used by portalocker.
    """

    def __init__(
        self,
        file_path: str | Path,
        mode: str = "a",
        create_mode: int = 0o644,
        shared: bool = False,
        timeout: timedelta | float | None = None,
        polling_interval: timedelta | float = timedelta(milliseconds=250),
        **fopen_kwargs: Any,
    ):
        """Create an asynchronous file lock."""
        self.file_path = Path(file_path)
        self.shared = shared
        self.create_mode = create_mode
        self.timeout = (
            timeout.total_seconds() if isinstance(timeout, timedelta) else timeout
        )
        self.mode: str = mode
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
            mode=self.mode,  # type: ignore
            timeout=0,
            flags=lock_flags,
            **self.fopen_kwargs,
        )

    async def __aenter__(self) -> IO[AnyStr]:
        """Attempt to acquire the file lock.

        The function will repeatedly attempt to acquire the underlying
        portalocker lock in a non-blocking fashion. Between attempts it
        sleeps for :attr:`polling_interval` seconds. If a timeout is set
        and exceeded a :class:`TimeoutError` is raised.

        :returns: The file-like object returned by portalocker's
            acquire (suitable for use as a file context manager).
        """
        start = time()
        while True:
            try:
                try:
                    self.file_path.touch(mode=self.create_mode, exist_ok=False)
                except FileExistsError:
                    pass
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
        """Release the previously acquired lock.

        The release operation delegates to :mod:`portalocker` and does
        not re-raise exceptions to the caller.
        """
        self.lock.release()
