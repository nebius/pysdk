from collections.abc import Awaitable

from nebius.aio.base import ChannelBase

DeferredChannel = Awaitable[ChannelBase]
