import sys
from asyncio import (
    FIRST_COMPLETED,
    AbstractEventLoop,
    CancelledError,
    Task,
    create_task,
    gather,
    get_event_loop,
    iscoroutine,
    new_event_loop,
    run_coroutine_threadsafe,
    sleep,
    wait,
)
from collections.abc import Awaitable, Coroutine, Sequence
from inspect import isawaitable
from logging import getLogger
from pathlib import Path
from typing import Any, TextIO, TypeVar

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
from nebius.aio.abc import GracefulInterface
from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
from nebius.aio.authorization.interceptor import AuthorizationInterceptor
from nebius.aio.authorization.token import TokenProvider
from nebius.aio.cli_config import Config as ConfigReader
from nebius.aio.idempotency import IdempotencyKeyInterceptor
from nebius.aio.service_descriptor import ServiceStub, from_stub_class
from nebius.aio.token import exchangeable, renewable
from nebius.aio.token.static import Bearer as StaticTokenBearer
from nebius.aio.token.static import EnvBearer
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
    Reader as ServiceAccountReader,
)
from nebius.base.service_account.service_account import (
    TokenRequester as TokenRequestReader,
)
from nebius.base.tls_certificates import get_system_certificates
from nebius.base.version import version

from .base import AddressChannel, ChannelBase

logger = getLogger(__name__)

Req = TypeVar("Req", bound=Message)
Res = TypeVar("Res", bound=Message)

T = TypeVar("T")


class LoopError(SDKError):
    pass


class ChannelClosedError(SDKError):
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
        ch = self._channel.get_channel_by_method(self._method)
        ret = ch.channel.unary_unary(  # type: ignore[unused-ignore,call-arg,assignment,misc]
            self._method,
            self._request_serializer,
            self._response_deserializer,
        )(  # type: ignore[unused-ignore,call-arg,assignment,misc]
            request,
            timeout=timeout,
            metadata=metadata,  # type: ignore
            credentials=credentials,
            wait_for_ready=wait_for_ready,
            compression=compression,
        )

        def return_channel(cb_arg: Any) -> None:
            nonlocal ch
            logger.debug(f"Done with call {self=}, {cb_arg=}")
            try:
                self._channel.discard_channel(ch)
            except ChannelClosedError:
                self._channel.run_sync(ch.channel.close(None), 0.1)
                # pass
            ch = None  # type: ignore

        ret.add_done_callback(return_channel)
        return ret  # type: ignore[unused-ignore,return-value]


class NoCredentials:
    pass


Credentials = (
    AuthorizationProvider
    | TokenBearer
    | TokenRequestReader
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


async def _run_awaitable_with_timeout(
    f: Awaitable[T],
    timeout: float | None = None,
) -> T:
    task = Task(_wrap_awaitable(f), name=f"Task for {f=}")
    tasks: list[Task[Any]] = list[Task[Any]]([task])
    if timeout is not None:
        timer = Task(sleep(timeout), name=f"Timer for {f=}")
        tasks.append(timer)
    done, pending = await wait(
        tasks,
        return_when=FIRST_COMPLETED,
    )
    for p in pending:
        logger.debug(f"Canceling pending task {p}")
        p.cancel()
    await gather(*pending, return_exceptions=True)
    try:
        if task.exception() is not None:
            if task not in done:
                raise TimeoutError("Awaitable timed out") from task.exception()
            raise task.exception()  # type: ignore
    except CancelledError as e:
        if task not in done:
            raise TimeoutError("Awaitable timed out") from e
        raise e
    return task.result()


def set_user_agent_option(
    user_agent: str, options: ChannelArgumentType | None
) -> ChannelArgumentType:
    options = list(options or [])
    options.append(("grpc.primary_user_agent", user_agent))
    return options


class Channel(ChannelBase):  # type: ignore[unused-ignore,misc]
    def __init__(
        self,
        *,
        resolver: Resolver | None = None,
        substitutions: dict[str, str] | None = None,
        user_agent_prefix: str | None = None,
        domain: str | None = None,
        options: ChannelArgumentType | None = None,
        interceptors: Sequence[ClientInterceptor] | None = None,
        address_options: dict[str, ChannelArgumentType] | None = None,
        address_interceptors: dict[str, Sequence[ClientInterceptor]] | None = None,
        credentials: Credentials = None,
        service_account_id: str | None = None,
        service_account_public_key_id: str | None = None,
        service_account_private_key_file_name: str | Path | None = None,
        credentials_file_name: str | Path | None = None,
        config_reader: ConfigReader | None = None,
        tls_credentials: ChannelCredentials | None = None,
        event_loop: AbstractEventLoop | None = None,
        max_free_channels_per_address: int = 2,
        parent_id: str | None = None,
        federation_invitation_writer: TextIO | None = None,
        federation_invitation_no_browser_open: bool = False,
    ) -> None:
        import nebius.api.nebius.iam.v1.token_exchange_service_pb2  # type: ignore[unused-ignore] # noqa: F401 - load for registration
        import nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc  # type: ignore[unused-ignore] # noqa: F401 - load for registration

        if domain is None:
            if config_reader is not None:
                domain = config_reader.endpoint()

            if domain is None or domain == "":
                domain = DOMAIN

        substitutions_full = dict[str, str]()
        substitutions_full["{domain}"] = domain
        if substitutions is not None:
            substitutions_full.update(substitutions)

        self._max_free_channels_per_address = max_free_channels_per_address

        self._gracefuls = set[GracefulInterface]()
        self._tasks = set[Task[Any]]()

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

        self._free_channels = dict[str, list[GRPCChannel]]()
        self._methods = dict[str, str]()
        self.user_agent = "nebius-python-sdk/" + version
        self.user_agent += f" (python/{sys.version_info.major}.{sys.version_info.minor}"
        self.user_agent += f".{sys.version_info.micro})"

        if user_agent_prefix is not None:
            self.user_agent = f"{user_agent_prefix} {self.user_agent}"

        if interceptors is None:
            interceptors = []
        self._global_options = options or []
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

        self._parent_id = parent_id
        if self._parent_id is None and config_reader is not None:
            from .cli_config import NoParentIdError

            try:
                self._parent_id = config_reader.parent_id
            except NoParentIdError:
                pass
        if self._parent_id == "":
            raise SDKError("Parent id is empty")

        self._token_bearer: TokenBearer | None = None
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
            elif config_reader is not None:
                credentials = config_reader.get_credentials(
                    self,
                    writer=federation_invitation_writer,
                    no_browser_open=federation_invitation_no_browser_open,
                )
            else:
                credentials = EnvBearer()
        if isinstance(credentials, str) or isinstance(credentials, Token):
            credentials = StaticTokenBearer(credentials)
        if isinstance(credentials, ServiceAccountReader):
            from nebius.aio.token.service_account import ServiceAccountBearer

            credentials = ServiceAccountBearer(
                credentials,
                self,
            )
        if isinstance(credentials, TokenRequestReader):
            exchange = exchangeable.Bearer(credentials, self)
            cache = renewable.Bearer(exchange)
            credentials = cache
        if isinstance(credentials, TokenBearer):
            self._gracefuls.add(credentials)
            self._token_bearer = credentials
            credentials = TokenProvider(credentials)
        if isinstance(credentials, AuthorizationProvider):
            self._global_interceptors_inner.append(
                AuthorizationInterceptor(credentials)
            )
        elif not isinstance(credentials, NoCredentials):  # type: ignore[unused-ignore]
            raise SDKError(f"credentials type is not supported: {type(credentials)}")

        self._event_loop = event_loop
        self._closed = False

        self._global_interceptors_inner.append(CleaningInterceptor())

    async def get_token(
        self,
        timeout: float | None,
        options: dict[str, str] | None = None,
    ) -> Token:
        if self._token_bearer is None:
            raise SDKError("Token bearer is not set")
        receiver = self._token_bearer.receiver()
        return await receiver.fetch(
            timeout=timeout,
            options=options,
        )

    def get_token_sync(
        self,
        timeout: float | None,
        options: dict[str, str] | None = None,
    ) -> Token:
        timeout_sync = timeout
        if timeout_sync is not None:
            timeout_sync += 0.2  # 200 ms for graceful shutdown
        return self.run_sync(
            self.get_token(timeout, options),
            timeout_sync,
        )

    def parent_id(self) -> str | None:
        return self._parent_id

    def bg_task(self, coro: Awaitable[T]) -> Task[None]:
        """Run a coroutine without awaiting or tracking, and log any exceptions."""

        async def wrapper() -> None:
            try:
                await coro
            except CancelledError:
                pass
            except Exception as e:
                logger.error("Unhandled exception in Channel.bg_task", exc_info=e)

        ret = create_task(wrapper(), name=f"Channel.bg_task for {coro}")
        ret.add_done_callback(lambda x: self._tasks.discard(x))
        self._tasks.add(ret)
        return ret

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
                            "another loop at the SDK initialization."
                        )
                except RuntimeError:
                    pass
                return run_coroutine_threadsafe(
                    _run_awaitable_with_timeout(awaitable, timeout),
                    self._event_loop,
                ).result()
            else:
                raise LoopError(
                    "Synchronous call inside async context. Either use "
                    "async/await or provide a safe and separate loop "
                    "to run at the SDK initialization."
                )

        return self._event_loop.run_until_complete(
            _run_awaitable_with_timeout(awaitable, timeout)
        )

    def sync_close(self, timeout: float | None = None) -> None:
        return self.run_sync(self.close(), timeout)

    async def close(self, grace: float | None = None) -> None:
        self._closed = True
        awaits = list[Coroutine[Any, Any, Any]]()
        for chans in self._free_channels.values():
            for chan in chans:
                awaits.append(chan.close(grace))
        for graceful in self._gracefuls:
            awaits.append(graceful.close(grace))
        for task in self._tasks:
            task.cancel()
        rets = await gather(*awaits, *self._tasks, return_exceptions=True)
        for ret in rets:
            if isinstance(ret, BaseException) and not isinstance(ret, CancelledError):
                logger.error(f"Error while graceful shutdown: {ret}", exc_info=ret)

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

    def get_channel_by_addr(self, addr: str) -> AddressChannel:
        if self._closed:
            raise ChannelClosedError("Channel closed")
        if addr not in self._free_channels:
            self._free_channels[addr] = []
        chans = self._free_channels[addr]
        while len(chans) > 0:
            chan = chans.pop()
            if chan.get_state() != ChannelConnectivity.SHUTDOWN:
                return AddressChannel(chan, addr)
            self.bg_task(chan.close(None))

        return self.create_address_channel(addr)

    def return_channel(self, chan: AddressChannel | None) -> None:
        if chan is None:
            return
        if self._closed:
            raise ChannelClosedError("Channel closed")
        if chan.address not in self._free_channels:
            self._free_channels[chan.address] = []
        if (
            chan.channel.get_state() != ChannelConnectivity.SHUTDOWN
            and len(self._free_channels[chan.address])
            < self._max_free_channels_per_address
        ):
            self._free_channels[chan.address].append(chan.channel)
        else:
            self.discard_channel(chan)

    def discard_channel(self, chan: AddressChannel | None) -> None:
        if chan is None:
            return
        if self._closed:
            raise ChannelClosedError("Channel closed")
        self.bg_task(chan.channel.close(None))

    def get_channel_by_method(self, method_name: str) -> AddressChannel:
        addr = self.get_addr_by_method(method_name)
        return self.get_channel_by_addr(addr)

    def get_address_options(self, addr: str) -> ChannelArgumentType:
        ret = [opt for opt in self._global_options]
        if addr in self._address_options:
            ret.extend(self._address_options[addr])
        ret = set_user_agent_option(self.user_agent, ret)  # type: ignore[assignment]
        return ret

    def get_address_interceptors(self, addr: str) -> Sequence[ClientInterceptor]:
        ret = [opt for opt in self._global_interceptors]
        if addr in self._address_interceptors:
            ret.extend(self._address_interceptors[addr])
        ret.extend(self._global_interceptors_inner)
        return ret

    def create_address_channel(self, addr: str) -> AddressChannel:
        logger.debug(f"creating channel for {addr=}")
        opts = self.get_address_options(addr)
        opts, insecure = pop_option(opts, INSECURE, bool)
        opts, compression = pop_option(opts, COMPRESSION, Compression)
        interceptors = self.get_address_interceptors(addr)
        if insecure:
            return AddressChannel(
                insecure_channel(addr, opts, compression, interceptors),  # type: ignore[unused-ignore,no-any-return]
                addr,
            )
        else:
            return AddressChannel(
                secure_channel(  # type: ignore[unused-ignore,no-any-return]
                    addr,
                    self._tls_credentials,
                    opts,
                    compression,
                    interceptors,
                ),
                addr,
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
        if self._closed:
            return ChannelConnectivity.SHUTDOWN
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
