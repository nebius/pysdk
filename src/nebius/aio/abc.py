from collections.abc import Awaitable
from typing import Protocol, TypeVar

from grpc.aio import Channel as GRPCChannel

T = TypeVar("T")


class SyncronizerInterface(Protocol):
    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T: ...


class ClientChannelInterface(Protocol):
    def get_channel_by_method(self, method_name: str) -> GRPCChannel: ...

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T: ...
