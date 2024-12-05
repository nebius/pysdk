from typing import Protocol

from grpc.aio import Channel as GRPCChannel


class ClientChannelInterface(Protocol):
    def get_channel_by_method(self, method_name: str) -> GRPCChannel: ...
