from collections.abc import Awaitable
from typing import TypeVar

from nebius.aio.abc import ClientChannelInterface

from .base import AddressChannel

T = TypeVar("T")


class Constant(ClientChannelInterface):
    def __init__(
        self,
        method: str,
        source: ClientChannelInterface,
        parent_id: str | None = None,
    ) -> None:
        self._method = method
        self._parent_id = parent_id or source.parent_id()
        self._source = source

    def return_channel(self, chan: AddressChannel | None) -> None:
        return self._source.return_channel(chan)

    def discard_channel(self, chan: AddressChannel | None) -> None:
        return self._source.discard_channel(chan)

    def parent_id(self) -> str | None:
        return self._parent_id

    def get_channel_by_method(self, method_name: str) -> AddressChannel:
        return self._source.get_channel_by_method(self._method)

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        return self._source.run_sync(awaitable, timeout)
