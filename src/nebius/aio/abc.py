"""Define asynchronous protocols for the SDK.

The channel and related components implement these small
:class:`typing.Protocol` interfaces. Applicable protocols support runtime
checks for unit tests.
"""

from collections.abc import Awaitable
from typing import Protocol, TypeVar, runtime_checkable

from .authorization.authorization import Provider as AuthorizationProvider
from .base import AddressChannel

T = TypeVar("T")


class SyncronizerInterface(Protocol):
    """Define objects that run awaitables synchronously.

    :meth:`run_sync` runs an awaitable on the object's event loop. It blocks
    the caller until the awaitable is complete.
    """

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        """Run ``awaitable`` to completion and return its result.

        :param awaitable: The awaitable to execute on the synchronizer's loop.
        :param timeout: Optional wall-clock timeout in seconds.
        :return: The result of the awaitable.
        """

        ...


@runtime_checkable
class ClientChannelInterface(Protocol):
    """Protocol describing the minimal channel operations required by
    SDK clients.

    Typical implementations are :class:`nebius.aio.channel.Channel` or
    simple test doubles that provide access to transport channels and
    authorization providers. The built-in channel additionally exposes
    ``run_async``. It schedules work immediately and returns a reusable
    cross-loop awaitable. That capability remains optional so existing custom
    channels which implement this minimal protocol keep their local-awaitable
    compatibility path.
    """

    def get_channel_by_method(self, method_name: str) -> AddressChannel:
        """Obtain an :class:`AddressChannel` for the specified RPC method.

        :param method_name: Fully-qualified RPC method name
            (``'/pkg.Service/Method'``).
        :return: An :class:`AddressChannel` for the resolved address.
        """

        ...

    def return_channel(self, chan: AddressChannel | None) -> None:
        """Return an :class:`AddressChannel` previously obtained from the
        channel back to the pool for reuse.
        """

        ...

    def discard_channel(self, chan: AddressChannel | None) -> None:
        """Discard an :class:`AddressChannel`, ensuring the underlying
        transport is closed and not reused.
        """

        ...

    def get_authorization_provider(self) -> AuthorizationProvider | None:
        """Get the configured :class:`AuthorizationProvider` or ``None``."""

        ...

    def parent_id(self) -> str | None:
        """Get the default parent id applied to some requests, or
        ``None`` if none was configured.
        """

        ...

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        """Run an awaitable synchronously using the channel's configured
        event loop and return the result.
        """

        ...


def release_address_channel(
    channel: ClientChannelInterface,
    chan: AddressChannel | None,
    *,
    discard: bool = False,
) -> None:
    """Release a transport through the SDK's non-masking lifecycle path.

    Older or custom channel implementations do not expose ``release_channel``;
    those retain the original return/discard behavior.
    """
    release = getattr(channel, "release_channel", None)
    if callable(release):
        release(chan, discard=discard)
    else:
        method = "discard_channel" if discard else "return_channel"
        callback = getattr(channel, method, None)
        if callable(callback):
            callback(chan)


class GracefulInterface(Protocol):
    """Define components that support controlled asynchronous shutdown.

    During shutdown, the channel calls :py:meth:`close`. This coroutine stops
    background tasks and releases resources.
    """

    async def close(self, grace: float | None = None) -> None:
        """Perform asynchronous shutdown of the component.

        :param grace: Optional grace period in seconds for the component to
            complete shutdown work.
        """

        ...
