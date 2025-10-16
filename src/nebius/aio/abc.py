"""Asyncio-related abstract protocols used by the SDK.

This module defines lightweight :class:`typing.Protocol` interfaces that the
channel and related components implement. The protocols are intentionally
minimal and runtime-checkable where appropriate so that implementations can
be validated in unit tests.
"""

from collections.abc import Awaitable
from typing import Protocol, TypeVar, runtime_checkable

from .authorization.authorization import Provider as AuthorizationProvider
from .base import AddressChannel

T = TypeVar("T")


class SyncronizerInterface(Protocol):
    """Protocol for objects capable of running awaitables synchronously.

    Implementations expose a single :meth:`run_sync` method which executes
    an awaitable on an event loop owned by the implementation and blocks the
    caller until completion.
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
    authorization providers.
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


class GracefulInterface(Protocol):
    """Protocol for components that support graceful asynchronous shutdown.

    Objects implementing this protocol expose an :py:meth:`close` coroutine
    that the channel will call during shutdown to allow background tasks and
    resources to be released.
    """

    async def close(self, grace: float | None = None) -> None:
        """Perform asynchronous shutdown of the component.

        :param grace: Optional grace period in seconds for the component to
            complete shutdown work.
        """

        ...
