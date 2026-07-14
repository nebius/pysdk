from __future__ import annotations

from typing import Any, cast

import grpc

from nebius.base.protos.reflection import ServiceDescriptor
from nebius.base.protos.registry import Registry


def add_service(
    server: grpc.Server, client_type: type[Any], implementation: object
) -> None:
    """Register a direct generated service implementation with a gRPC server."""
    descriptor = cast(ServiceDescriptor, client_type.get_descriptor())
    registry = cast(Registry, client_type.__registry__)
    handlers: dict[str, grpc.RpcMethodHandler[Any, Any]] = {}

    for method in descriptor.methods:
        behavior = getattr(implementation, method.name, None)
        if behavior is None:
            continue
        request_type = registry.message_class(method.input_type.full_name)
        response_type = registry.message_class(method.output_type.full_name)
        kwargs = {
            "request_deserializer": request_type.FromString,
            "response_serializer": response_type.SerializeToString,
        }
        if method.client_streaming and method.server_streaming:
            handler = grpc.stream_stream_rpc_method_handler(behavior, **kwargs)
        elif method.client_streaming:
            handler = grpc.stream_unary_rpc_method_handler(behavior, **kwargs)
        elif method.server_streaming:
            handler = grpc.unary_stream_rpc_method_handler(behavior, **kwargs)
        else:
            handler = grpc.unary_unary_rpc_method_handler(behavior, **kwargs)
        handlers[method.name] = handler

    server.add_generic_rpc_handlers(
        (grpc.method_handlers_generic_handler(descriptor.full_name, handlers),)
    )
