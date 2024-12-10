from typing import Any, Protocol, TypeVar

from google.protobuf.message import Message
from grpc import (
    CallCredentials,
    ChannelConnectivity,
    Compression,
)
from grpc.aio import Channel as GRPCChannel
from grpc.aio._base_call import (
    StreamStreamCall,
    StreamUnaryCall,
    UnaryStreamCall,
    UnaryUnaryCall,
)
from grpc.aio._base_channel import (
    StreamStreamMultiCallable,
    StreamUnaryMultiCallable,
    UnaryStreamMultiCallable,
    UnaryUnaryMultiCallable,
)
from grpc.aio._typing import (
    DeserializingFunction,
    MetadataType,
    RequestIterableType,
    SerializingFunction,
)

from nebius.base.error import SDKError
from nebius.base.methods import service_from_method_name

Req = TypeVar("Req", bound=Message)
Res = TypeVar("Res", bound=Message)


class NotATrueCallError(SDKError):
    def __init__(self, *args: object) -> None:
        super().__init__("This class is not meant to be run as a call.")


class NoMethodsInServiceError(SDKError):
    def __init__(self, *args: object) -> None:
        super().__init__("Mo methods found in service stub")


class StubUU(UnaryUnaryMultiCallable):  # type: ignore[unused-ignore,misc,type-arg]
    def __call__(  # type: ignore
        self,
        request,  # type: ignore[unused-ignore]
        *,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> UnaryUnaryCall:  # type: ignore[unused-ignore, type-arg]
        raise NotATrueCallError()


class StubUS(UnaryStreamMultiCallable):  # type: ignore[unused-ignore,misc,type-arg]
    def __call__(  # type: ignore
        self,
        request,  # type: ignore[unused-ignore]
        *,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> UnaryStreamCall:  # type: ignore[unused-ignore, type-arg]
        raise NotATrueCallError()


class StubSU(StreamUnaryMultiCallable):  # type: ignore[unused-ignore,misc]
    def __call__(  # type: ignore[unused-ignore]
        self,
        request_iterator: RequestIterableType | None = None,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> StreamUnaryCall:  # type: ignore[unused-ignore, type-arg]
        raise NotATrueCallError()


class StubSS(StreamStreamMultiCallable):  # type: ignore[unused-ignore,misc]
    def __call__(  # type: ignore[unused-ignore]
        self,
        request_iterator: RequestIterableType | None = None,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> StreamStreamCall:  # type: ignore[unused-ignore, type-arg]
        raise NotATrueCallError()


class ExtractorChannel(GRPCChannel):  # type: ignore[unused-ignore,misc]
    def __init__(self) -> None:
        super().__init__()
        self._last_method = ""

    def get_service_name(self) -> str:
        if self._last_method == "":
            raise NoMethodsInServiceError()
        return service_from_method_name(self._last_method)

    def unary_unary(  # type: ignore[unused-ignore, override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = False,
    ) -> UnaryUnaryMultiCallable[Req, Res]:  # type: ignore[unused-ignore, override]
        self._last_method = method
        return StubUU()

    async def close(self, grace: float | None = None) -> None:
        pass

    async def __aenter__(self) -> "ExtractorChannel":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close(None)

    def get_state(self, try_to_connect: bool = False) -> ChannelConnectivity:
        return ChannelConnectivity.READY

    async def wait_for_state_change(
        self,
        last_observed_state: ChannelConnectivity,
    ) -> None:
        raise NotImplementedError("this method has no meaning for this channel")

    async def channel_ready(self) -> None:
        return

    def unary_stream(  # type: ignore[override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = None,
    ) -> UnaryStreamMultiCallable[Req, Res]:  # type: ignore[unused-ignore]
        self._last_method = method
        raise StubUS()  # type: ignore[misc]

    def stream_unary(  # type: ignore[override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = None,
    ) -> StreamUnaryMultiCallable:
        self._last_method = method
        raise StubSU()  # type: ignore[misc]

    def stream_stream(  # type: ignore[override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = None,
    ) -> StreamStreamMultiCallable:
        self._last_method = method
        raise StubSS()  # type: ignore[misc]


class ServiceStub(Protocol):
    def __init__(self, channel: GRPCChannel) -> None: ...


def from_stub_class(stub: type[ServiceStub]) -> str:
    if hasattr(stub, "__PB2_NAME__"):
        return getattr(stub, "__PB2_NAME__")  # type: ignore[no-any-return]
    extractor = ExtractorChannel()
    _ = stub(extractor)
    ret = extractor.get_service_name()
    setattr(stub, "__PB2_NAME__", ret)
    return ret
