"""Extract service names from gRPC service stubs.

The placeholder calls prevent network requests. An extractor channel records
service metadata for the Nebius asynchronous SDK.
"""

from typing import Any, Protocol, TypeVar

from google.protobuf.message import Message
from grpc import CallCredentials, ChannelConnectivity, Compression
from grpc.aio import Channel as GRPCChannel
from grpc.aio._base_call import StreamStreamCall, StreamUnaryCall, UnaryStreamCall, UnaryUnaryCall
from grpc.aio._base_channel import (
    StreamStreamMultiCallable,
    StreamUnaryMultiCallable,
    UnaryStreamMultiCallable,
    UnaryUnaryMultiCallable,
)
from grpc.aio._typing import DeserializingFunction, RequestIterableType, SerializingFunction

from ..base.error import SDKError
from ..base.methods import service_from_method_name
from ._metadata_type import MetadataType

Req = TypeVar("Req", bound=Message)
Res = TypeVar("Res", bound=Message)


class NotATrueCallError(SDKError):
    """Report an attempt to run an introspection stub.

    Placeholder stubs raise this error because they record service metadata.
    They do not make RPCs.
    """

    def __init__(self, *args: object) -> None:
        super().__init__("This class is not meant to be run as a call.")


class NoMethodsInServiceError(SDKError):
    """Report a service stub that has no gRPC methods.

    Service-name extraction raises this error when it cannot record a method.
    """

    def __init__(self, *args: object) -> None:
        super().__init__("No methods found in service stub")


class StubUU(UnaryUnaryMultiCallable):  # type: ignore[unused-ignore,misc,type-arg]
    """Represent a unary-unary gRPC method during introspection.

    A call raises :class:`NotATrueCallError` and does not make an RPC.
    """

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
        raise NotATrueCallError


class StubUS(UnaryStreamMultiCallable):  # type: ignore[unused-ignore,misc,type-arg]
    """Represent a unary-stream gRPC method during introspection.

    A call raises :class:`NotATrueCallError` and does not make an RPC.
    """

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
        raise NotATrueCallError


class StubSU(StreamUnaryMultiCallable):  # type: ignore[unused-ignore,misc]
    """Represent a stream-unary gRPC method during introspection.

    A call raises :class:`NotATrueCallError` and does not make an RPC.
    """

    def __call__(  # type: ignore[unused-ignore]
        self,
        request_iterator: RequestIterableType | None = None,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> StreamUnaryCall:  # type: ignore[unused-ignore, type-arg]
        raise NotATrueCallError


class StubSS(StreamStreamMultiCallable):  # type: ignore[unused-ignore,misc]
    """Represent a stream-stream gRPC method during introspection.

    A call raises :class:`NotATrueCallError` and does not make an RPC.
    """

    def __call__(  # type: ignore[unused-ignore]
        self,
        request_iterator: RequestIterableType | None = None,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> StreamStreamCall:  # type: ignore[unused-ignore, type-arg]
        raise NotATrueCallError


class ExtractorChannel(GRPCChannel):  # type: ignore[unused-ignore,misc]
    """Extract service names from gRPC stub classes.

    This channel records the last method that a stub calls. It gets the service
    name from that method and does not make a network request.
    """

    def __init__(self) -> None:
        super().__init__()
        self._last_method = ""

    def get_service_name(self) -> str:
        """Return the service name from the last recorded method.

        :return: The service name.
        :rtype: str
        :raises NoMethodsInServiceError: If no methods have been recorded.
        """
        if self._last_method == "":
            raise NoMethodsInServiceError
        return service_from_method_name(self._last_method)

    def unary_unary(  # type: ignore[unused-ignore, override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = False,
    ) -> UnaryUnaryMultiCallable[Req, Res]:  # type: ignore[unused-ignore, override]
        """Record a unary-unary method call and return a stub.

        :param method: The method name.
        :type method: str
        :param request_serializer: Optional request serializer.
        :type request_serializer: ``SerializingFunction`` or ``None``
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: ``DeserializingFunction`` or ``None``
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: ``UnaryUnaryMultiCallable``
        """
        self._last_method = method
        return StubUU()

    async def close(self, grace: float | None = None) -> None:
        """Return without an action because this channel has no connection.

        :param grace: Optional grace period.
        :type grace: float or None
        """

    async def __aenter__(self) -> "ExtractorChannel":
        """Enter the asynchronous context.

        :return: Self.
        :rtype: :class:`ExtractorChannel`
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the asynchronous context.

        :param exc_type: Exception type.
        :type exc_type: Any
        :param exc_val: Exception value.
        :type exc_val: Any
        :param exc_tb: Exception traceback.
        :type exc_tb: Any
        """
        await self.close(None)

    def get_state(self, try_to_connect: bool = False) -> ChannelConnectivity:
        """Return ``READY`` for this introspection channel.

        :param try_to_connect: Whether to attempt connection.
        :type try_to_connect: bool
        :return: The connectivity state.
        :rtype: :class:`ChannelConnectivity`
        """
        return ChannelConnectivity.READY

    async def wait_for_state_change(
        self,
        last_observed_state: ChannelConnectivity,
    ) -> None:
        """Reject a state-change wait for this introspection channel.

        :param last_observed_state: The last observed state.
        :type last_observed_state: :class:`ChannelConnectivity`
        :raises NotImplementedError: Always raised.
        """
        raise NotImplementedError("this method has no meaning for this channel")

    async def channel_ready(self) -> None:
        """Return immediately because this introspection channel is ready."""
        return

    def unary_stream(  # type: ignore[override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = None,
    ) -> UnaryStreamMultiCallable[Req, Res]:  # type: ignore[unused-ignore]
        """Record a unary-stream method call and return a stub.

        :param method: The method name.
        :type method: str
        :param request_serializer: Optional request serializer.
        :type request_serializer: ``SerializingFunction`` or ``None``
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: ``DeserializingFunction`` or ``None``
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: ``UnaryStreamMultiCallable``
        """
        self._last_method = method
        return StubUS()

    def stream_unary(  # type: ignore[override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = None,
    ) -> StreamUnaryMultiCallable:
        """Record a stream-unary method call and return a stub.

        :param method: The method name.
        :type method: str
        :param request_serializer: Optional request serializer.
        :type request_serializer: ``SerializingFunction`` or ``None``
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: ``DeserializingFunction`` or ``None``
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: ``StreamUnaryMultiCallable``
        """
        self._last_method = method
        return StubSU()

    def stream_stream(  # type: ignore[override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
        _registered_method: bool | None = None,
    ) -> StreamStreamMultiCallable:
        """Record a stream-stream method call and return a stub.

        :param method: The method name.
        :type method: str
        :param request_serializer: Optional request serializer.
        :type request_serializer: ``SerializingFunction`` or ``None``
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: ``DeserializingFunction`` or ``None``
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: ``StreamStreamMultiCallable``
        """
        self._last_method = method
        return StubSS()


class ServiceStub(Protocol):
    """Define gRPC service stub classes that accept a channel."""

    def __init__(self, channel: GRPCChannel) -> None: ...


def from_stub_class(stub: type[ServiceStub]) -> str:
    """Return the service name from a gRPC stub class.

    Create the stub with an :class:`ExtractorChannel`. The channel records a
    method and returns its service name.

    :param stub: The stub class to extract from.
    :type stub: ``type[ServiceStub]``
    :return: The service name.
    :rtype: str
    """
    if hasattr(stub, "__PB2_NAME__"):
        return getattr(stub, "__PB2_NAME__")  # type: ignore[no-any-return]
    service_name = getattr(stub, "__service_name__", None)
    if isinstance(service_name, str):
        return service_name.lstrip(".")
    extractor = ExtractorChannel()
    _ = stub(extractor)
    ret = extractor.get_service_name()
    setattr(stub, "__PB2_NAME__", ret)
    return ret
