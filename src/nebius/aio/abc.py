from collections.abc import Awaitable
from typing import Protocol, TypeVar, runtime_checkable

from .authorization.authorization import Provider as AuthorizationProvider
from .base import AddressChannel

T = TypeVar("T")


class SyncronizerInterface(Protocol):
    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T: ...


@runtime_checkable
class ClientChannelInterface(Protocol):
    def get_channel_by_method(self, method_name: str) -> AddressChannel: ...
    def return_channel(self, chan: AddressChannel | None) -> None: ...
    def discard_channel(self, chan: AddressChannel | None) -> None: ...
    def get_authorization_provider(self) -> AuthorizationProvider | None: ...

    def parent_id(self) -> str | None: ...

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T: ...


class GracefulInterface(Protocol):
    async def close(self, grace: float | None = None) -> None: ...
