from grpc.aio import Channel as GRPCChannel


class AddressChannel:
    def __init__(self, channel: GRPCChannel, address: str) -> None:
        self.address = address
        self.channel = channel


class ChannelBase(GRPCChannel):
    pass
