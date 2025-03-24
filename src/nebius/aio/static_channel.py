from collections.abc import Awaitable
from typing import TypeVar

from grpc.aio import Channel as GRPCChannel

from nebius.aio.abc import ClientChannelInterface, SyncronizerInterface

T = TypeVar("T")


class Static(ClientChannelInterface):
    def __init__(
        self,
        channel: GRPCChannel,
        syncronizer: SyncronizerInterface,
    ) -> None:
        self._channel = channel
        self._syncronizer = syncronizer

    def get_channel_by_method(self, method_name: str) -> GRPCChannel:
        return self._channel

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        return self._syncronizer.run_sync(awaitable, timeout)
