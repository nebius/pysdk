from collections.abc import Awaitable

from nebius.aio.abc import ClientChannelInterface

DeferredChannel = Awaitable[ClientChannelInterface]
