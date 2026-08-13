"""Define base classes for generated SDK clients.

Generated clients inherit these small base classes. The classes wrap a
``ClientChannelInterface`` and supply a ``request`` factory for generated RPC
methods.

Application code must not create these types directly. They supply a common
structure for code generated from service definitions.
"""

from collections.abc import AsyncIterable, Callable, Iterable
from logging import getLogger
from typing import Any, Generic, TypeVar

from typing_extensions import Unpack

from .abc import ClientChannelInterface as Channel
from .constant_channel import Constant
from .request import Request

# from ..api.nebius.common.v1 import Operation
from .request_kwargs import RequestKwargs
from .route import Route
from .stream import StreamRequest

Req = TypeVar("Req")
Res = TypeVar("Res")


class Client:
    """Lightweight base class for generated service clients.

    Each generated service subclass must set ``__service_name__``. Its RPC
    methods call :meth:`request` to construct a
    :class:`nebius.aio.request.Request`.

    :cvar __service_name__: Fully qualified service name for RPC routes.
    :cvar __api_service_name__: Optional API gateway name for service routes.
    :cvar __registry__: Descriptor registry for request metadata.
    :cvar __service_deprecation_details__: Optional deprecation message. The
        client writes this message to the warning log when it starts.

    :param channel: a channel implementing :class:`ClientChannelInterface`
    :type channel: :class:`ClientChannelInterface`
    """

    # __operation_type__: Message = Operation
    __service_name__: str
    __api_service_name__: str = ""
    __registry__: object | None = None
    __service_deprecation_details__: str | None = None

    def __init__(self, channel: Channel) -> None:
        """Create a client bound to a channel."""
        self._channel = channel

        if self.__service_deprecation_details__ is not None:
            getLogger("deprecation").warning(
                f"Service {self.__service_name__} is deprecated. {self.__service_deprecation_details__}",
                stack_info=True,
                stacklevel=2,
            )

    def request(
        self,
        method: str,
        request: Req,
        result_pb2_class: type[Any],
        result_wrapper: Callable[[str, Channel, Any], Res] | None = None,
        **kwargs: Unpack[RequestKwargs],
    ) -> Request[Req, Res]:
        """Construct a :class:`nebius.aio.request.Request` for an RPC.

        Subclasses' generated RPC methods call this helper to create a
        Request object with the appropriate service/method names and options.

        :param method: RPC method name (bare, without service prefix)
        :type method: `str`
        :param request: protobuf message or request payload accepted by the RPC
        :param result_pb2_class: protobuf class of the RPC response message
        :type result_pb2_class: type of the protobuf result message
        :param result_wrapper: optional callable to post-process the RPC result

        Other keyword arguments are passed through to the
        :class:`nebius.aio.request.Request` constructor.
        See :class:`nebius.aio.request_kwargs.RequestKwargs` for details.

        :returns: a configured :class:`nebius.aio.request.Request` instance
        :rtype: :class:`Request` of the return type of the RPC or the result of
            ``result_wrapper`` if provided.
        """
        return Request[Req, Res](
            channel=self._channel,
            service=self.__service_name__,
            method=method,
            request=request,
            result_pb2_class=result_pb2_class,
            result_wrapper=result_wrapper,
            route=Route(
                service=self.__service_name__,
                method=method,
                api_service_name=self.__api_service_name__,
                registry=self.__registry__,
            ),
            **kwargs,
        )

    def stream_request(
        self,
        method: str,
        request: Req | AsyncIterable[Req] | Iterable[Req] | None,
        result_class: type[Res],
        *,
        client_streaming: bool,
        server_streaming: bool,
        **kwargs: Any,
    ) -> StreamRequest[Req, Res]:
        """Construct a native async request for a streaming RPC shape."""
        return StreamRequest(
            channel=self._channel,
            route=Route(
                service=self.__service_name__,
                method=method,
                api_service_name=self.__api_service_name__,
                registry=self.__registry__,
            ),
            request=request,
            result_class=result_class,
            client_streaming=client_streaming,
            server_streaming=server_streaming,
            **kwargs,
        )


OperationPb = TypeVar("OperationPb")
OperationService = TypeVar("OperationService", bound=Client)


class ClientWithOperations(Client, Generic[OperationPb, OperationService]):
    """Extension of :class:`Client` for services that manage long-running operations.

    :meth:`operation_service` creates an operation client when first called.
    It caches this client. A constant channel routes the client to the
    service's operation methods.

    :cvar __operation_type__: the protobuf message class used to represent
        long-running operations.
    :cvar __operation_service_class__: the client class used to manage
        operations.
    :cvar __operation_source_method__: the method name used to identify
        the source of operations for this service (for example, "CreateFoo"
        if the service's "CreateFoo" method returns operations).
    :ivar __operation_service__: cached instance of the operation-service client.

    :param channel: channel used for normal RPCs; a special constant
        channel will be created for the operation service when needed.
    """

    __operation_type__: type[OperationPb]
    __operation_service_class__: type[OperationService]
    __operation_source_method__: str

    def __init__(self, channel: Channel) -> None:
        """Initialize the client-with-operations."""
        super().__init__(channel)
        self.__operation_service__: OperationService | None = None

    def operation_service(self) -> OperationService:
        """Return a cached operation-service client instance.

        The first call creates and caches the operation-service client. Its
        type is ``__operation_service_class__``. A
        :class:`nebius.aio.constant_channel.Constant` routes calls to the
        operation endpoint.

        :returns: an instance of the operation service client
        :rtype: OperationService
        """
        if self.__operation_service__ is None:
            self.__operation_service__ = self.__operation_service_class__(
                Constant(
                    self.__service_name__ + "." + self.__operation_source_method__,
                    self._channel,
                ),
            )
        return self.__operation_service__
