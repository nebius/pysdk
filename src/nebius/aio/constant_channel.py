"""A tiny channel implementation that routes all calls to a single
service/method combination.

The :class:`Constant` channel wraps an existing
:class:`ClientChannelInterface`. It resolves all method lookups to one
specified ``method`` name. Generated helpers use it for clients that target
one service-method namespace. These clients reuse the source channel's
network and authorization functions.
"""

from collections.abc import Awaitable
from typing import TypeVar

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.authorization.authorization import Provider as AuthorizationProvider

from .base import AddressChannel

T = TypeVar("T")


class Constant(ClientChannelInterface):
    """Channel that proxies requests to a single constant method.

    :param method: the fully-qualified method name (service.method) to route to
    :param source: an existing :class:`ClientChannelInterface` that performs
        authorization, pooling, and other channel operations
    :param parent_id: optional parent id to override the source's parent id
    """

    def __init__(
        self,
        method: str,
        source: ClientChannelInterface,
        parent_id: str | None = None,
    ) -> None:
        """Initialize the constant channel."""
        self._method = method
        self._parent_id = parent_id or source.parent_id()
        self._source = source

    def return_channel(self, chan: AddressChannel | None) -> None:
        """Return a previously-acquired address channel to the source.

        This forwards to the wrapped source channel's :meth:`return_channel`.

        :param chan: the channel to return
        :type chan: :class:`AddressChannel` or `None`
        """
        return self._source.return_channel(chan)

    def discard_channel(self, chan: AddressChannel | None) -> None:
        """Discard an address channel previously acquired from the source.

        This forwards to the wrapped source channel's :meth:`discard_channel`.

        :param chan: the channel to discard
        :type chan: :class:`AddressChannel` or `None`
        """
        return self._source.discard_channel(chan)

    def release_channel(
        self,
        chan: AddressChannel | None,
        *,
        discard: bool = False,
    ) -> None:
        """Release a channel through the source's non-masking lifecycle path."""
        release = getattr(self._source, "release_channel", None)
        if callable(release):
            release(chan, discard=discard)
        elif discard:
            self._source.discard_channel(chan)
        else:
            self._source.return_channel(chan)

    def parent_id(self) -> str | None:
        """Return the effective parent id for this constant channel.

        If a parent id was provided to the constructor it is returned; otherwise
        the source channel's parent id is used.

        :returns: the parent id `str` or `None`
        """
        return self._parent_id

    def get_authorization_provider(self) -> AuthorizationProvider | None:
        """Return the authorization provider used by the underlying source
        channel (if any).

        :returns: :class:`AuthorizationProvider` or `None`
        """
        return self._source.get_authorization_provider()

    def get_channel_by_method(self, method_name: str) -> AddressChannel:
        """Resolve an address channel by method name.

        The provided ``method_name`` is ignored; this implementation always
        returns the address channel associated with the constant ``method``
        provided at construction time.

        :param method_name: ignored
        :type method_name: str
        :returns: an :class:`AddressChannel` for the constant method
        """
        return self._source.get_channel_by_method(self._method)

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        """Synchronously run an awaitable using the source channel's
        synchronization helper.

        :param awaitable: an awaitable to execute
        :param timeout: optional timeout forwarded to the source implementation
        :type timeout: `float` or `None`
        :returns: the awaitable result
        """
        return self._source.run_sync(awaitable, timeout)
