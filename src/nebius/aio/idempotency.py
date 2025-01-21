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

Req = TypeVar("Req")
Res = TypeVar("Res")


def new_key() -> str:
    return str(uuid4())


def add_key_to_metadata(metadata: Metadata | GRPCMetadata) -> None:
    log.debug("added idempotency key to metadata")
    metadata[HEADER] = new_key()


def ensure_key_in_metadata(metadata: Metadata | GRPCMetadata) -> None:
    if HEADER not in metadata or metadata[HEADER] == "" or metadata[HEADER] == [""]:
        add_key_to_metadata(metadata)


class IdempotencyKeyInterceptor(UnaryUnaryClientInterceptor):  # type: ignore[unused-ignore,misc]
    async def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, Req], UnaryUnaryCall | Res],
        client_call_details: ClientCallDetails,
        request: Req,
    ) -> UnaryUnaryCall | Res:
        if client_call_details.metadata is None:
            client_call_details.metadata = GRPCMetadata()
        ensure_key_in_metadata(client_call_details.metadata)
        return await continuation(client_call_details, request)  # type: ignore
