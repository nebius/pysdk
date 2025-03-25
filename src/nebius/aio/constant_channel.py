from collections.abc import Awaitable
from typing import TypeVar

from grpc.aio import Channel as GRPCChannel

from nebius.aio.abc import ClientChannelInterface

T = TypeVar("T")


class Constant(ClientChannelInterface):
    def __init__(
        self,
        method: str,
        source: ClientChannelInterface,
    ) -> None:
        self._method = method
        self._source = source

    def get_channel_by_method(self, method_name: str) -> GRPCChannel:
        return self._source.get_channel_by_method(self._method)

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        return self._source.run_sync(awaitable, timeout)
