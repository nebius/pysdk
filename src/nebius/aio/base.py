"""Thin wrappers around the underlying gRPC channel used by the SDK.

This module exposes two small helper classes:

- :class:`AddressChannel` pairs a :class:`grpc.aio.Channel` with the
  resolved address string used to create it. The SDK uses this wrapper to
  keep track of which transport channel corresponds to which logical
  endpoint.
- :class:`ChannelBase` is a small subclass of the gRPC channel type. Use it
  for SDK channels where code expects :class:`grpc.aio.Channel`.
"""

from asyncio import AbstractEventLoop, get_event_loop, get_running_loop
from threading import Lock

from grpc.aio import Channel as GRPCChannel


class AddressChannel:
    """Simple container for a gRPC channel and its resolved address.

    :ivar address: Resolved address string used to create the channel.
    :type address: str
    :ivar channel: The underlying gRPC channel instance.
    :type channel: :class:`grpc.aio.Channel`
    :ivar event_loop: Event loop that owns the underlying gRPC channel.
    :type event_loop: optional :class:`asyncio.AbstractEventLoop`

    :param channel: The underlying :class:`grpc.aio.Channel` instance.
    :param address: The resolved address string (for example ``'host:port'``)
      that was used to create the channel.
    :param event_loop: Event loop that owns ``channel``. This is optional for
      compatibility with callers constructing an ``AddressChannel`` directly.
      When omitted, ownership is inferred from the running or current loop.
      Callers wrapping a channel created elsewhere should pass its owner loop
      explicitly because this inference is only best effort.
    """

    address: str
    channel: GRPCChannel
    event_loop: AbstractEventLoop | None

    def __init__(
        self,
        channel: GRPCChannel,
        address: str,
        event_loop: AbstractEventLoop | None = None,
    ) -> None:
        """Initialize an :class:`AddressChannel` instance."""
        self.address = address
        self.channel = channel
        self._close_state_lock = Lock()
        self._closed_by_sdk = False
        if event_loop is None:
            try:
                event_loop = get_running_loop()
            except RuntimeError:
                try:
                    event_loop = get_event_loop()
                except RuntimeError:
                    pass
        self.event_loop = event_loop

    def _mark_closed_by_sdk(self) -> None:
        """Record that SDK lifecycle management closed this transport."""

        with self._close_state_lock:
            self._closed_by_sdk = True

    def _is_closed_by_sdk(self) -> bool:
        """Return whether SDK lifecycle management closed this transport."""

        with self._close_state_lock:
            return self._closed_by_sdk


class ChannelBase(GRPCChannel):
    """Base class used for SDK channel implementations.

    SDK components accept this type when they require the SDK extensions to a
    gRPC channel.
    """

    pass
