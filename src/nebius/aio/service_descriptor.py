"""Service descriptor utilities for gRPC services.

This module provides classes and functions to extract service names from gRPC
stub classes and handle service method descriptors in the Nebius async SDK.
It includes stub implementations that prevent actual calls and an extractor
channel for introspecting service metadata.
"""

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
    """Error raised when attempting to call a stub method that is not meant to be
    executed.

    This exception is used by stub classes in this module to indicate that they
    are placeholders for service introspection, not actual callable methods.
    """

    def __init__(self, *args: object) -> None:
        super().__init__("This class is not meant to be run as a call.")


class NoMethodsInServiceError(SDKError):
    """Error raised when no methods are found in a service stub.

    This exception occurs during service name extraction if the stub class
    does not define any gRPC methods.
    """

    def __init__(self, *args: object) -> None:
        super().__init__("No methods found in service stub")


class StubUU(UnaryUnaryMultiCallable):  # type: ignore[unused-ignore,misc,type-arg]
    """Stub implementation for unary-unary gRPC methods.

    This class raises NotATrueCallError when called, as it is used only for
    service introspection, not actual RPC execution.
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
        raise NotATrueCallError()


class StubUS(UnaryStreamMultiCallable):  # type: ignore[unused-ignore,misc,type-arg]
    """Stub implementation for unary-stream gRPC methods.

    This class raises NotATrueCallError when called, as it is used only for
    service introspection, not actual RPC execution.
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
        raise NotATrueCallError()


class StubSU(StreamUnaryMultiCallable):  # type: ignore[unused-ignore,misc]
    """Stub implementation for stream-unary gRPC methods.

    This class raises NotATrueCallError when called, as it is used only for
    service introspection, not actual RPC execution.
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
        raise NotATrueCallError()


class StubSS(StreamStreamMultiCallable):  # type: ignore[unused-ignore,misc]
    """Stub implementation for stream-stream gRPC methods.

    This class raises NotATrueCallError when called, as it is used only for
    service introspection, not actual RPC execution.
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
        raise NotATrueCallError()


class ExtractorChannel(GRPCChannel):  # type: ignore[unused-ignore,misc]
    """A mock gRPC channel for extracting service names from stub classes.

    This channel implementation records the last method called on it and can
    extract the service name from the method name. It is used to introspect
    gRPC stub classes without making actual network calls.
    """

    def __init__(self) -> None:
        super().__init__()
        self._last_method = ""

    def get_service_name(self) -> str:
        """Extract the service name from the last recorded method.

        :return: The service name.
        :rtype: str
        :raises NoMethodsInServiceError: If no methods have been recorded.
        """
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
        """Record a unary-unary method call and return a stub.

        :param method: The method name.
        :type method: str
        :param request_serializer: Optional request serializer.
        :type request_serializer: :class:`SerializingFunction` or None
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: :class:`DeserializingFunction` or None
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: :class:`UnaryUnaryMultiCallable`
        """
        self._last_method = method
        return StubUU()

    async def close(self, grace: float | None = None) -> None:
        """Close the channel (no-op for this mock implementation).

        :param grace: Optional grace period.
        :type grace: float or None
        """
        pass

    async def __aenter__(self) -> "ExtractorChannel":
        """Enter async context.

        :return: Self.
        :rtype: :class:`ExtractorChannel`
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context.

        :param exc_type: Exception type.
        :type exc_type: Any
        :param exc_val: Exception value.
        :type exc_val: Any
        :param exc_tb: Exception traceback.
        :type exc_tb: Any
        """
        await self.close(None)

    def get_state(self, try_to_connect: bool = False) -> ChannelConnectivity:
        """Get the channel state (always READY for this mock).

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
        """Wait for state change (not implemented for this mock).

        :param last_observed_state: The last observed state.
        :type last_observed_state: :class:`ChannelConnectivity`
        :raises NotImplementedError: Always raised.
        """
        raise NotImplementedError("this method has no meaning for this channel")

    async def channel_ready(self) -> None:
        """Wait for channel to be ready (no-op for this mock)."""
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
        :type request_serializer: :class:`SerializingFunction` or None
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: :class:`DeserializingFunction` or None
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: :class:`UnaryStreamMultiCallable`
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
        :type request_serializer: :class:`SerializingFunction` or None
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: :class:`DeserializingFunction` or None
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: :class:`StreamUnaryMultiCallable`
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
        :type request_serializer: :class:`SerializingFunction` or None
        :param response_deserializer: Optional response deserializer.
        :type response_deserializer: :class:`DeserializingFunction` or None
        :param _registered_method: Whether the method is registered.
        :type _registered_method: bool or None
        :return: A stub callable.
        :rtype: :class:`StreamStreamMultiCallable`
        """
        self._last_method = method
        return StubSS()


class ServiceStub(Protocol):
    """Protocol for gRPC service stub classes.

    This protocol defines the expected interface for gRPC stub classes
    that can be instantiated with a channel.
    """

    def __init__(self, channel: GRPCChannel) -> None: ...


def from_stub_class(stub: type[ServiceStub]) -> str:
    """Extract the service name from a gRPC stub class.

    Uses an ExtractorChannel to instantiate the stub and record method calls,
    then extracts the service name from the recorded method.

    :param stub: The stub class to extract from.
    :type stub: type[:class:`ServiceStub`]
    :return: The service name.
    :rtype: str
    """
    if hasattr(stub, "__PB2_NAME__"):
        return getattr(stub, "__PB2_NAME__")  # type: ignore[no-any-return]
    extractor = ExtractorChannel()
    _ = stub(extractor)
    ret = extractor.get_service_name()
    setattr(stub, "__PB2_NAME__", ret)
    return ret
