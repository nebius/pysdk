"""Namespace-aware transport calls for current and alpha operation services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from grpc.aio import Channel

    from nebius.base.protos.registry import Registry


class OperationServiceTransportStub:
    """Small generated-code-free equivalent of the operation gRPC stub."""

    def __init__(
        self,
        channel: Channel,
        registry: Registry,
        *,
        alpha: bool = False,
    ) -> None:
        package = "nebius.common.v1alpha1" if alpha else "nebius.common.v1"
        get_request = registry.message_class(f"{package}.GetOperationRequest")
        list_request = registry.message_class(f"{package}.ListOperationsRequest")
        operation = registry.message_class(f"{package}.Operation")
        list_response = registry.message_class(f"{package}.ListOperationsResponse")
        service = f"/{package}.OperationService"
        self.Get = channel.unary_unary(
            f"{service}/Get",
            request_serializer=_serialize,
            response_deserializer=operation.FromString,
        )
        self.List = channel.unary_unary(
            f"{service}/List",
            request_serializer=_serialize,
            response_deserializer=list_response.FromString,
        )
        self._request_types = (get_request, list_request)


def _serialize(message: Any) -> bytes:
    return cast(bytes, message.SerializeToString())
