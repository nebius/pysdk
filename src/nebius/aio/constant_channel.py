"""A channel implementation that routes all calls to one service/method combination.

The :class:`Constant` channel wraps an existing
:class:`ClientChannelInterface`. It resolves all method lookups to one
specified ``method`` name. Generated helpers use it for clients that target
one service-method namespace. These clients reuse the source channel's
network and authorization functions.
"""

from collections.abc import Awaitable
from typing import TypeVar, cast

from .abc import ClientChannelInterface
from .authorization.authorization import Provider as AuthorizationProvider
from .base import AddressChannel
from .route import Route

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
        method: str | Route,
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

    def get_authorization_provider(
        self,
    ) -> AuthorizationProvider | None:
        """Return the authorization provider used by the underlying source channel.

        :returns: :class:`AuthorizationProvider` or `None`
        """
        return self._source.get_authorization_provider()

    def _has_authorization_provider(self) -> bool | None:
        """Return whether the source has a fixed authorization provider.

        Legacy sources do not expose the private caller-safe probe. Their auth
        timeout remains enforced by the request's authorization loop instead
        of by a speculative caller-side dispatch deadline.

        :return: ``True`` or ``False`` when the source can answer safely, or
            ``None`` when provider discovery belongs to its owner loop.
        """
        provider_probe = getattr(self._source, "_has_authorization_provider", None)
        if not callable(provider_probe):
            return None
        result = provider_probe()
        return None if result is None else bool(result)

    def get_channel_by_method(self, method_name: str) -> AddressChannel:
        """Resolve an address channel by method name.

        The provided ``method_name`` is ignored; this implementation always
        returns the address channel associated with the constant ``method``
        provided at construction time.

        :param method_name: ignored
        :type method_name: str
        :returns: an :class:`AddressChannel` for the constant method
        """
        if isinstance(self._method, Route):
            routed = getattr(self._source, "get_channel_by_route", None)
            if callable(routed):
                return cast(AddressChannel, routed(self._method))
            return self._source.get_channel_by_method(self._method.method_name)
        return self._source.get_channel_by_method(self._method)

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        """Synchronously run an awaitable using the source channel's helper.

        :param awaitable: an awaitable to execute
        :param timeout: optional timeout forwarded to the source implementation
        :type timeout: `float` or `None`
        :returns: the awaitable result
        """
        return self._source.run_sync(awaitable, timeout)

    def run_async(self, awaitable: Awaitable[T]) -> Awaitable[T]:
        """Submit an awaitable to the source channel's SDK event loop.

        A legacy source without ``run_async`` returns the original awaitable.
        Callers that retain the result must schedule a one-shot coroutine on
        their active loop before memoizing it.

        :param awaitable: Work to submit or return for legacy execution.
        :return: Source submission handle, or the unchanged awaitable.
        """
        submit = getattr(self._source, "run_async", None)
        if callable(submit):
            return cast(Awaitable[T], submit(awaitable))
        return awaitable
