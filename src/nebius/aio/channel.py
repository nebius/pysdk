from asyncio import (
    AbstractEventLoop,
    gather,
    get_event_loop,
    iscoroutine,
    new_event_loop,
    run_coroutine_threadsafe,
    wait_for,
)
from collections.abc import Awaitable, Coroutine, Sequence
from inspect import isawaitable
from logging import getLogger
from typing import Any, TypeVar

from google.protobuf.message import Message
from grpc import (
    CallCredentials,
    ChannelConnectivity,
    ChannelCredentials,
    Compression,
    ssl_channel_credentials,
)
from grpc.aio import Channel as GRPCChannel
from grpc.aio._base_call import UnaryUnaryCall
from grpc.aio._base_channel import (
    StreamStreamMultiCallable,
    StreamUnaryMultiCallable,
    UnaryStreamMultiCallable,
    UnaryUnaryMultiCallable,
)
from grpc.aio._channel import (
    insecure_channel,  # type: ignore[unused-ignore]
    secure_channel,  # type: ignore[unused-ignore]
)
from grpc.aio._interceptor import ClientInterceptor
from grpc.aio._typing import (
    ChannelArgumentType,
    DeserializingFunction,
    MetadataType,
    SerializingFunction,
)

from nebius.aio._cleaner import CleaningInterceptor
from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
from nebius.aio.authorization.interceptor import AuthorizationInterceptor
from nebius.aio.authorization.token import TokenProvider
from nebius.aio.idempotency import IdempotencyKeyInterceptor
from nebius.aio.service_descriptor import ServiceStub, from_stub_class
from nebius.aio.token import exchangeable, renewable
from nebius.aio.token.static import Bearer as StaticTokenBearer
from nebius.aio.token.token import Bearer as TokenBearer
from nebius.aio.token.token import Token
from nebius.api.nebius.common.v1.operation_service_pb2_grpc import (
    OperationServiceStub,
)
from nebius.api.nebius.common.v1alpha1.operation_service_pb2_grpc import (
    OperationServiceStub as OperationServiceStubDeprecated,
)
from nebius.base.constants import DOMAIN
from nebius.base.error import SDKError
from nebius.base.methods import service_from_method_name
from nebius.base.options import COMPRESSION, INSECURE, pop_option
from nebius.base.resolver import Chain, Conventional, Resolver, TemplateExpander
from nebius.base.service_account.service_account import (
    TokenRequester as ServiceAccountReader,
)
from nebius.base.tls_certificates import get_system_certificates

from .base import ChannelBase

logger = getLogger(__name__)

Req = TypeVar("Req", bound=Message)
Res = TypeVar("Res", bound=Message)

T = TypeVar("T")


class LoopError(SDKError):
    pass


class NebiusUnaryUnaryMultiCallable(UnaryUnaryMultiCallable[Req, Res]):  # type: ignore[unused-ignore,misc]
    def __init__(
        self,
        channel: "Channel",
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> None:
        super().__init__()
        self._channel = channel
        self._method = method
        self._request_serializer = request_serializer
        self._response_deserializer = response_deserializer
        self._true_callee: UnaryUnaryMultiCallable[Req, Res] | None = None

    def __call__(
        self,
        request: Req,
        *,
        timeout: float | None = None,
        metadata: MetadataType | None = None,
        credentials: CallCredentials | None = None,
        wait_for_ready: bool | None = None,
        compression: Compression | None = None,
    ) -> UnaryUnaryCall[Req, Res]:
        if self._true_callee is None:
            ch = self._channel.get_channel_by_method(self._method)
            self._true_callee = ch.unary_unary(  # type: ignore[unused-ignore,call-arg,assignment]
                self._method,
                self._request_serializer,
                self._response_deserializer,
            )
        return self._true_callee(  # type: ignore[unused-ignore,misc]
            request,
            timeout=timeout,
            metadata=metadata,
            credentials=credentials,
            wait_for_ready=wait_for_ready,
            compression=compression,
        )


class NoCredentials:
    pass


Credentials = (
    AuthorizationProvider
    | TokenBearer
    | ServiceAccountReader
    | NoCredentials
    | Token
    | str
    | None
)


def _wrap_awaitable(awaitable: Awaitable[T]) -> Coroutine[Any, Any, T]:
    if iscoroutine(awaitable):
        return awaitable
    if not isawaitable(awaitable):
        raise TypeError(
            "An asyncio.Future, a coroutine or an awaitable is "
            + f"required, {type(awaitable)} given"
        )

    async def wrap() -> T:
        return await awaitable

    return wrap()


class Channel(ChannelBase):  # type: ignore[unused-ignore,misc]
    def __init__(
        self,
        *,
        resolver: Resolver | None = None,
        substitutions: dict[str, str] | None = None,
        domain: str = DOMAIN,
        options: ChannelArgumentType | None = None,
        interceptors: Sequence[ClientInterceptor] | None = None,
        address_options: dict[str, ChannelArgumentType] | None = None,
        address_interceptors: dict[str, Sequence[ClientInterceptor]] | None = None,
        credentials: Credentials = None,
        service_account_id: str | None = None,
        service_account_public_key_id: str | None = None,
        service_account_private_key_file_name: str | None = None,
        credentials_file_name: str | None = None,
        tls_credentials: ChannelCredentials | None = None,
        event_loop: AbstractEventLoop | None = None,
    ) -> None:
        import nebius.api.nebius.iam.v1.token_exchange_service_pb2  # type: ignore[unused-ignore] # noqa: F401 - load for registration
        import nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc  # noqa: F401 - load for registration

        substitutions_full = dict[str, str]()
        substitutions_full["{domain}"] = domain
        if substitutions is not None:
            substitutions_full.update(substitutions)

        self._resolver: Resolver = Conventional()
        if resolver is not None:
            self._resolver = Chain(resolver, self._resolver)
        self._resolver = TemplateExpander(substitutions_full, self._resolver)
        if tls_credentials is None:
            root_ca = get_system_certificates()
            with open(root_ca, "rb") as f:
                trusted_certs = f.read()
            tls_credentials = ssl_channel_credentials(root_certificates=trusted_certs)
        self._tls_credentials = tls_credentials

        self._channels = dict[str, GRPCChannel]()
        self._methods = dict[str, str]()

        if options is None:
            options = []
        if interceptors is None:
            interceptors = []
        self._global_options = options
        self._global_interceptors: list[ClientInterceptor] = [
            IdempotencyKeyInterceptor()
        ]
        self._global_interceptors.extend(interceptors)

        if address_options is None:
            address_options = dict[str, ChannelArgumentType]()
        if address_interceptors is None:
            address_interceptors = dict[str, Sequence[ClientInterceptor]]()
        self._address_options = address_options
        self._address_interceptors = address_interceptors

        self._global_interceptors_inner: list[ClientInterceptor] = []

        if credentials is None:
            if credentials_file_name is not None:
                from nebius.base.service_account.credentials_file import (
                    Reader as CredentialsFileReader,
                )

                credentials = CredentialsFileReader(credentials_file_name)
            elif (
                service_account_id is not None
                and service_account_private_key_file_name is not None
                and service_account_public_key_id is not None
            ):
                from nebius.base.service_account.pk_file import Reader as PKFileReader

                credentials = PKFileReader(
                    service_account_private_key_file_name,
                    service_account_public_key_id,
                    service_account_id,
                )

        if isinstance(credentials, str) or isinstance(credentials, Token):
            credentials = StaticTokenBearer(credentials)
        if isinstance(credentials, ServiceAccountReader):
            exchange = exchangeable.Bearer(credentials, self)
            cache = renewable.Bearer(exchange)
            credentials = cache
        if isinstance(credentials, TokenBearer):
            credentials = TokenProvider(credentials)
        if isinstance(credentials, AuthorizationProvider):
            self._global_interceptors_inner.append(
                AuthorizationInterceptor(credentials)
            )
        self._event_loop = event_loop

        self._global_interceptors_inner.append(CleaningInterceptor())

    def run_sync(self, awaitable: Awaitable[T], timeout: float | None = None) -> T:
        loop_provided = self._event_loop is not None
        if self._event_loop is None:
            try:
                self._event_loop = get_event_loop()
            except RuntimeError:
                self._event_loop = new_event_loop()

        if self._event_loop.is_running():
            if loop_provided:
                try:
                    if get_event_loop() == self._event_loop:
                        raise LoopError(
                            "Provided loop is equal to current thread's "
                            "loop. Either use async/await or provide "
                            "another loop."
                        )
                except RuntimeError:
                    pass
                awaitable = _wrap_awaitable(awaitable)
                return run_coroutine_threadsafe(awaitable, self._event_loop).result(
                    timeout
                )
            else:
                raise LoopError(
                    "Synchronous call inside async context. Either use "
                    "async/await or provide a safe and separate loop "
                    "to run."
                )

        return self._event_loop.run_until_complete(wait_for(awaitable, timeout))

    def sync_close(self, timeout: float | None = None) -> None:
        return self.run_sync(self.close(), timeout)

    async def close(self, grace: float | None = None) -> None:
        awaits = list[Coroutine[Any, Any, Any]]()
        for chan in self._channels.values():
            awaits.append(chan.close(grace))
        await gather(*awaits)

    def get_corresponding_operation_service(
        self,
        service_stub_class: type[ServiceStub],
    ) -> OperationServiceStub:
        addr = self.get_addr_from_stub(service_stub_class)
        chan = self.get_channel_by_addr(addr)
        return OperationServiceStub(chan)  # type: ignore[no-untyped-call]

    def get_corresponding_operation_service_alpha(
        self,
        service_stub_class: type[ServiceStub],
    ) -> OperationServiceStubDeprecated:
        addr = self.get_addr_from_stub(service_stub_class)
        chan = self.get_channel_by_addr(addr)
        return OperationServiceStubDeprecated(chan)  # type: ignore[no-untyped-call]

    def get_addr_from_stub(self, service_stub_class: type[ServiceStub]) -> str:
        service = from_stub_class(service_stub_class)
        return self.get_addr_from_service_name(service)

    def get_addr_from_service_name(self, service_name: str) -> str:
        if len(service_name) > 1 and service_name[0] == ".":
            service_name = service_name[1:]
        return self._resolver.resolve(service_name)

    def get_addr_by_method(self, method_name: str) -> str:
        if method_name not in self._methods:
            service_name = service_from_method_name(method_name)
            self._methods[method_name] = self.get_addr_from_service_name(service_name)
        return self._methods[method_name]

    def get_channel_by_addr(self, addr: str) -> GRPCChannel:
        if addr not in self._channels:
            self._channels[addr] = self.create_address_channel(addr)
        return self._channels[addr]

    def get_channel_by_method(self, method_name: str) -> GRPCChannel:
        addr = self.get_addr_by_method(method_name)
        return self.get_channel_by_addr(addr)

    def get_address_options(self, addr: str) -> ChannelArgumentType:
        ret = [opt for opt in self._global_options]
        if addr in self._address_options:
            ret.extend(self._address_options[addr])
        return ret

    def get_address_interceptors(self, addr: str) -> Sequence[ClientInterceptor]:
        ret = [opt for opt in self._global_interceptors]
        if addr in self._address_interceptors:
            ret.extend(self._address_interceptors[addr])
        ret.extend(self._global_interceptors_inner)
        return ret

    def create_address_channel(self, addr: str) -> GRPCChannel:
        opts = self.get_address_options(addr)
        opts, insecure = pop_option(opts, INSECURE, bool)
        opts, compression = pop_option(opts, COMPRESSION, Compression)
        interceptors = self.get_address_interceptors(addr)
        if insecure:
            return insecure_channel(addr, opts, compression, interceptors)  # type: ignore[unused-ignore,no-any-return]
        else:
            return secure_channel(  # type: ignore[unused-ignore,no-any-return]
                addr,
                self._tls_credentials,
                opts,
                compression,
                interceptors,
            )

    def unary_unary(  # type: ignore[unused-ignore,override]
        self,
        method_name: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> UnaryUnaryMultiCallable[Req, Res]:  # type: ignore[unused-ignore,override]
        return NebiusUnaryUnaryMultiCallable(
            self,
            method_name,
            request_serializer,
            response_deserializer,
        )

    async def __aenter__(self) -> "Channel":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close(None)

    def get_state(self, try_to_connect: bool = False) -> ChannelConnectivity:
        return ChannelConnectivity.READY

    async def wait_for_state_change(
        self,
        last_observed_state: ChannelConnectivity,
    ) -> None:
        raise NotImplementedError("this method has no meaning for this channel")

    async def channel_ready(self) -> None:
        return

    def unary_stream(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> UnaryStreamMultiCallable[Req, Res]:  # type: ignore[unused-ignore]
        raise NotImplementedError("Method not implemented")

    def stream_unary(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> StreamUnaryMultiCallable:
        raise NotImplementedError("Method not implemented")

    def stream_stream(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> StreamStreamMultiCallable:
        raise NotImplementedError("Method not implemented")
