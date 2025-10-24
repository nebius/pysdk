"""Idempotency key interceptor for gRPC aio clients.

This module provides functionality to automatically add idempotency keys to
gRPC client calls, ensuring that operations can be safely retried without
causing duplicate side effects on the server.

The interceptor adds a unique UUID4 key to the 'x-idempotency-key' header
for each call that doesn't already have one.
"""

from collections.abc import Callable
from logging import getLogger
from typing import TypeVar
from uuid import uuid4

from grpc.aio._call import UnaryUnaryCall
from grpc.aio._interceptor import ClientCallDetails, UnaryUnaryClientInterceptor
from grpc.aio._metadata import Metadata as GRPCMetadata

from nebius.base.metadata import Metadata

log = getLogger(__name__)

HEADER = "x-idempotency-key"
"""The gRPC metadata header name used for idempotency keys."""

Req = TypeVar("Req")
Res = TypeVar("Res")


def new_key() -> str:
    """Generate a new idempotency key.

    :returns: A new UUID4 string to use as an idempotency key.
    """
    return str(uuid4())


def add_key_to_metadata(metadata: Metadata | GRPCMetadata) -> None:
    """Add a new idempotency key to the provided metadata.

    :param metadata: The metadata object to add the key to.
    """
    log.debug("added idempotency key to metadata")
    metadata[HEADER] = new_key()


def ensure_key_in_metadata(metadata: Metadata | GRPCMetadata) -> None:
    """Ensure an idempotency key is present in the metadata.

    If no idempotency key exists or it's empty, a new one is added.

    :param metadata: The metadata object to check and potentially modify.
    """
    if HEADER not in metadata or metadata[HEADER] == "" or metadata[HEADER] == [""]:
        add_key_to_metadata(metadata)


class IdempotencyKeyInterceptor(UnaryUnaryClientInterceptor):  # type: ignore[unused-ignore,misc]
    """gRPC client interceptor that adds idempotency keys to unary-unary calls.

    This interceptor ensures that every gRPC call has an idempotency key in its
    metadata, which helps prevent duplicate operations on the server side.
    """

    async def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, Req], UnaryUnaryCall | Res],
        client_call_details: ClientCallDetails,
        request: Req,
    ) -> UnaryUnaryCall | Res:
        """Intercept a unary-unary gRPC call and ensure idempotency key is present.

        :param continuation: The next interceptor in the chain or the actual call.
        :param client_call_details: Details of the client call, including metadata.
        :param request: The request payload.
        :returns: The result of the gRPC call.
        """
        if client_call_details.metadata is None:
            client_call_details.metadata = GRPCMetadata()
        ensure_key_in_metadata(client_call_details.metadata)
        return await continuation(client_call_details, request)  # type: ignore
