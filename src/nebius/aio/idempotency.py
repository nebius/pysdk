"""Add idempotency keys to asynchronous gRPC client calls.

The interceptor adds a unique UUID4 key to the ``x-idempotency-key`` header.
It does not replace an existing key. The key lets the server prevent duplicate
effects when a client retries an operation.
"""

from collections.abc import Callable
from logging import getLogger
from typing import TypeVar
from uuid import uuid4

from grpc.aio._call import UnaryUnaryCall
from grpc.aio._interceptor import ClientCallDetails, UnaryUnaryClientInterceptor
from grpc.aio._metadata import Metadata as GRPCMetadata

from ..base.metadata import Metadata

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
    """Add a new idempotency key to the metadata.

    :param metadata: The metadata object to add the key to.
    """
    log.debug("added idempotency key to metadata")
    metadata[HEADER] = new_key()


def ensure_key_in_metadata(metadata: Metadata | GRPCMetadata) -> None:
    """Ensure an idempotency key is present in the metadata.

    Add a new key if the metadata has no key or has an empty key.

    :param metadata: The metadata object to check and potentially modify.
    """
    if HEADER not in metadata or metadata[HEADER] == "" or metadata[HEADER] == [""]:
        add_key_to_metadata(metadata)


class IdempotencyKeyInterceptor(UnaryUnaryClientInterceptor):  # type: ignore[unused-ignore,misc]
    """Add idempotency keys to unary-unary gRPC calls.

    The idempotency key lets the server prevent duplicate operations.
    """

    async def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, Req], UnaryUnaryCall | Res],  # type: ignore[type-arg,unused-ignore]
        client_call_details: ClientCallDetails,
        request: Req,
    ) -> UnaryUnaryCall | Res:  # type: ignore[type-arg,unused-ignore]
        """Add an idempotency key to a unary-unary gRPC call.

        :param continuation: The next interceptor in the chain or the actual call.
        :param client_call_details: Details of the client call, including metadata.
        :param request: The request payload.
        :returns: The result of the gRPC call.
        """
        if client_call_details.metadata is None:
            client_call_details.metadata = GRPCMetadata()
        ensure_key_in_metadata(client_call_details.metadata)
        return await continuation(client_call_details, request)  # type: ignore
