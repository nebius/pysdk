from collections.abc import Callable
from logging import getLogger
from time import time
from typing import TypeVar

from grpc import StatusCode
from grpc.aio._call import AioRpcError, UnaryUnaryCall
from grpc.aio._interceptor import ClientCallDetails, UnaryUnaryClientInterceptor
from grpc.aio._metadata import Metadata

from nebius.base.metadata import Authorization, Internal

from .authorization import Provider

log = getLogger(__name__)

Req = TypeVar("Req")
Res = TypeVar("Res")


class AuthorizationInterceptor(UnaryUnaryClientInterceptor):  # type: ignore[unused-ignore,misc]
    def __init__(self, provider: Provider) -> None:
        super().__init__()
        self._provider = provider

    async def intercept_unary_unary(
        self,
        continuation: Callable[[ClientCallDetails, Req], UnaryUnaryCall | Res],
        client_call_details: ClientCallDetails,
        request: Req,
    ) -> UnaryUnaryCall | Res:
        auth_type = None
        if client_call_details.metadata is not None:
            auth_type = client_call_details.metadata.get(Internal.AUTHORIZATION)
        else:
            client_call_details.metadata = Metadata()
        if auth_type == Authorization.DISABLE:
            log.debug(
                f"Calling {client_call_details.method}," " authentication is disabled"
            )
            return await continuation(client_call_details, request)  # type: ignore

        log.debug(
            f"Authentication for {client_call_details.method} is enabled, "
            f"auth type: {auth_type!r}"
        )
        start = time()
        deadline = None
        if client_call_details.timeout is not None:
            deadline = start + client_call_details.timeout
        attempt = 0
        auth = self._provider.authenticator()
        while True:
            attempt += 1
            timeout = None
            if deadline is not None:
                timeout = deadline - time()
            log.debug(
                f"Authenticating {client_call_details.method},"
                f" attempt: {attempt}, timeout: {timeout}."
            )
            await auth.authenticate(client_call_details.metadata, timeout)
            if deadline is not None:
                if deadline <= time():
                    raise TimeoutError("authorization timed out")
                client_call_details.timeout = deadline - time()
            try:
                log.debug(f"Calling authenticated {client_call_details.method}.")
                return await continuation(client_call_details, request)  # type: ignore
            except AioRpcError as e:
                if (
                    e.code() != StatusCode.UNAUTHENTICATED
                    or not auth.can_retry(e)
                    or (deadline is not None and deadline <= time())
                ):
                    raise
                log.debug(
                    f"Call to {client_call_details.method},"
                    f" returned UNAUTHENTICATED, trying authentication again"
                )
