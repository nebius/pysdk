"""Base client classes used by generated SDK clients.

This module contains small, reusable base classes that concrete generated
clients inherit from. The classes provide a thin wrapper around a
``ClientChannelInterface`` and a convenience ``request`` factory used by the
generated RPC methods.

The types in this module are intentionally lightweight and are not meant to
be instantiated directly by application code; instead they provide a common
shaping layer for code generated from service definitions.
"""

from collections.abc import Callable
from logging import getLogger
from typing import Any, Generic, TypeVar

from google.protobuf.message import Message as PMessage
from typing_extensions import Unpack

from nebius.aio.abc import ClientChannelInterface as Channel
from nebius.aio.constant_channel import Constant
from nebius.aio.request import Request

# from nebius.api.nebius.common.v1 import Operation
from nebius.aio.request_kwargs import RequestKwargs

Req = TypeVar("Req")
Res = TypeVar("Res")


class Client:
    """Lightweight base class for generated service clients.

    Subclasses generated for each service should set the ``__service_name__``
    class attribute and expose RPC methods that in turn call
    :meth:`request` to construct a :class:`nebius.aio.request.Request`.

    :cvar __service_name__: the fully-qualified service name used in RPC
        routing (string).
    :cvar __service_deprecation_details__: optional deprecation message
        emitted as a runtime warning when the client is constructed.

    :param channel: a channel implementing :class:`ClientChannelInterface`
    :type channel: :class:`ClientChannelInterface`
    """

    # __operation_type__: Message = Operation
    __service_name__: str
    __service_deprecation_details__: str | None = None

    def __init__(self, channel: Channel) -> None:
        """Create a client bound to a channel."""
        self._channel = channel

        if self.__service_deprecation_details__ is not None:
            getLogger("deprecation").warning(
                f"Service {self.__service_name__} is deprecated. "
                f"{self.__service_deprecation_details__}",
                stack_info=True,
                stacklevel=2,
            )

    def request(
        self,
        method: str,
        request: Req,
        result_pb2_class: type[PMessage],
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
            **kwargs,
        )


OperationPb = TypeVar("OperationPb")
OperationService = TypeVar("OperationService", bound=Client)


class ClientWithOperations(Client, Generic[OperationPb, OperationService]):
    """Extension of :class:`Client` for services that manage long-running
    operations.

    This helper provides an :meth:`operation_service` accessor that lazily creates
    and caches a small helper client bound to a synthetic constant channel
    that targets the service's operation methods.

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

        The operation-service client is created on first access and cached on
        the instance. The created client is an instance of the
        ``__operation_service_class__`` and is bound to a
        :class:`nebius.aio.constant_channel.Constant` that routes calls to the
        service's operation endpoint.

        :returns: an instance of the operation service client
        :rtype: OperationService
        """
        if self.__operation_service__ is None:
            self.__operation_service__ = self.__operation_service_class__(
                Constant(
                    self.__service_name__ + "." + self.__operation_source_method__,
                    self._channel,
                )
            )
        return self.__operation_service__
