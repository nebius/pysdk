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
from copy import copy
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
    _close_state_lock: Lock
    _retired_by_sdk: bool
    _closed_by_sdk: bool
    _legacy_close_state_init_lock = Lock()

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
        self._retired_by_sdk = False
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

        close_state_lock = self._ensure_close_state()
        with close_state_lock:
            self._retired_by_sdk = True
            self._closed_by_sdk = True

    def _new_lease(self) -> "AddressChannel":
        """Create a fresh wrapper for another lease of this transport.

        A fresh wrapper prevents an old holder from releasing a later lease.
        Custom wrappers can override this method when they must preserve
        additional wrapper state.

        :return: New wrapper for the same native channel and owner loop.
        """

        lease = copy(self)
        lease._close_state_lock = Lock()
        lease._retired_by_sdk = False
        lease._closed_by_sdk = False
        return lease

    def _retire_by_sdk(self) -> bool:
        """Atomically reserve this transport for SDK-managed closure.

        :return: ``True`` only for the caller that changed the transport from
            reusable to retired. Later close attempts return ``False``.

        Retirement is permanent even when an owner loop stops before the
        native close can finish. A transport whose close was requested must
        never re-enter a pool while that close is pending or after its owner
        loop becomes available again.
        """

        close_state_lock = self._ensure_close_state()
        with close_state_lock:
            if getattr(self, "_retired_by_sdk", False):
                return False
            self._retired_by_sdk = True
            return True

    def _is_retired_by_sdk(self) -> bool:
        """Return whether SDK lifecycle management reserved this transport."""

        close_state_lock = self._ensure_close_state()
        with close_state_lock:
            return getattr(self, "_retired_by_sdk", False)

    def _is_closed_by_sdk(self) -> bool:
        """Return whether SDK lifecycle management closed this transport."""

        close_state_lock = self._ensure_close_state()
        with close_state_lock:
            return self._closed_by_sdk

    def _ensure_close_state(self) -> Lock:
        """Initialize lifecycle state for legacy subclasses that skipped init.

        Older custom wrappers sometimes override :meth:`__init__` without
        calling this base class. The class lock makes lazy initialization
        atomic while preserving that compatibility.

        :return: Per-wrapper lock protecting the SDK-close marker.
        """

        try:
            close_state_lock = self._close_state_lock
        except AttributeError:
            pass
        else:
            return close_state_lock
        with self._legacy_close_state_init_lock:
            try:
                close_state_lock = self._close_state_lock
            except AttributeError:
                close_state_lock = Lock()
                self._close_state_lock = close_state_lock
                self._retired_by_sdk = False
                self._closed_by_sdk = False
            return close_state_lock


class ChannelBase(GRPCChannel):
    """Base class used for SDK channel implementations.

    SDK components accept this type when they require the SDK extensions to a
    gRPC channel.
    """

    pass
