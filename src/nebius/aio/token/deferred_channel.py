"""Type alias for deferred client channel objects.

Examples
--------

Used in deferred token bearer implementations::

    from nebius.aio.token.deferred_channel import DeferredChannel
    from nebius.aio.abc import ClientChannelInterface
    from nebius.aio.token.service_account import ServiceAccountBearer
    from asyncio import Future

    chan: DeferredChannel = Future[ClientChannelInterface]()
    bearer = ServiceAccountBearer(..., channel=chan)

    sdk = SDK(credentials=bearer)
    chan.set_result(sdk)
"""

from collections.abc import Awaitable

from nebius.aio.abc import ClientChannelInterface

DeferredChannel = Awaitable[ClientChannelInterface]
"""Deferred client channel type.

Used in deferred token bearer implementations::

    from nebius.aio.token.deferred_channel import DeferredChannel
    from nebius.aio.abc import ClientChannelInterface
    from nebius.aio.token.service_account import ServiceAccountBearer
    from asyncio import Future

    chan: DeferredChannel = Future[ClientChannelInterface]()
    bearer = ServiceAccountBearer(..., channel=chan)

    sdk = SDK(credentials=bearer)
    chan.set_result(sdk)
"""
