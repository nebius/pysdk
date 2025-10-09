from collections.abc import Callable
from logging import getLogger
from typing import TypeVar

from grpc.aio._call import UnaryUnaryCall
from grpc.aio._interceptor import ClientCallDetails, UnaryUnaryClientInterceptor

from nebius.base import metadata

HEADER = "X-Idempotency-Key"

Req = TypeVar("Req")
Res = TypeVar("Res")

log = getLogger(__name__)


class CleaningInterceptor(UnaryUnaryClientInterceptor):  # type: ignore[unused-ignore,misc]
    async def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, Req], UnaryUnaryCall | Res],
        client_call_details: ClientCallDetails,
        request: Req,
    ) -> UnaryUnaryCall | Res:
        if client_call_details.metadata is not None:
            to_delete = {
                k
                for k, _ in client_call_details.metadata
                if k.lower().startswith(metadata.Internal.PREFIX.lower())
            }
            for k in to_delete:
                client_call_details.metadata.delete_all(k)
        return await continuation(client_call_details, request)  # type: ignore
