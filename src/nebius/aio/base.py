"""Thin wrappers around the underlying gRPC channel used by the SDK.

This module exposes two small helper classes:

- :class:`AddressChannel` pairs a :class:`grpc.aio.Channel` with the
  resolved address string used to create it. The SDK uses this wrapper to
  keep track of which transport channel corresponds to which logical
  endpoint.
- :class:`ChannelBase` is a trivial subclass of the gRPC channel type used
  to annotate and accept SDK-style channels where a :class:`grpc.aio.Channel`
  is expected.
"""

from grpc.aio import Channel as GRPCChannel


class AddressChannel:
    """Simple container for a gRPC channel and its resolved address.

    :ivar address: Resolved address string used to create the channel.
    :type address: str
    :ivar channel: The underlying gRPC channel instance.
    :type channel: :class:`grpc.aio.Channel`

    :param channel: The underlying :class:`grpc.aio.Channel` instance.
    :param address: The resolved address string (for example ``'host:port'``)
      that was used to create the channel.
    """

    address: str
    channel: GRPCChannel

    def __init__(self, channel: GRPCChannel, address: str) -> None:
        """Initialize an :class:`AddressChannel` instance."""
        self.address = address
        self.channel = channel


class ChannelBase(GRPCChannel):
    """Base class used for SDK channel implementations.

    This trivial subclass exists primarily for type clarity: SDK components
    can accept a :class:`ChannelBase` to indicate they expect a gRPC channel
    implementing the SDK's extended behavior.
    """

    pass
