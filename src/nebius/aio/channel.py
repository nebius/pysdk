"""High-level gRPC channel manager for the Nebius Python SDK."""

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

from nebius.aio.abc import GracefulInterface
from nebius.aio.authorization.authorization import Provider as AuthorizationProvider
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
    """Exception raised when a synchronous helper is used incorrectly with
    an asyncio event loop.

    This error is raised when the code attempts to perform a synchronous
    operation (for example, calling :meth:`Channel.run_sync`) while the
    targeted asyncio event loop is already running in the current thread.

    The exception subclasses :class:`SDKError` so callers
    catching SDK-related errors will also catch this condition.

    ``LoopError`` does not add any new behaviour beyond the base error; it
    serves only to provide a more specific error type for loop misuse.
    """


class ChannelClosedError(SDKError):
    """Raised when an operation is attempted on a closed :class:`Channel`.

    This indicates that :meth:`Channel.close` (or :meth:`Channel.sync_close`)
    was previously called and the channel no longer accepts requests or
    returns channel objects.
    """


class NebiusUnaryUnaryMultiCallable(UnaryUnaryMultiCallable[Req, Res]):  # type: ignore[unused-ignore,misc]
    """A small callable wrapper that binds RPC calls to a Channel-managed
    address channel.

    Instances of this class behave like a gRPC :class:`UnaryUnaryMultiCallable`
    but ensure that the underlying transport channel is obtained from the
    SDK :class:`Channel` pool and returned (or discarded) when the RPC
    completes.
    """

    def __init__(
        self,
        channel: "Channel",
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> None:
        """Create a callable wrapper that returns requests bound to an
        :class:`AddressChannel` from the SDK :class:`Channel`.

        :param channel: The SDK :class:`Channel` instance used to obtain a
            transport channel for the RPC.
        :param method: Full RPC method string (``'/package.service/Method'``).
        :param request_serializer: Optional serializer used by gRPC.
        :param response_deserializer: Optional deserializer used by gRPC.
        """
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
        """Invoke the underlying unary-unary RPC on an address channel.

        This method resolves the concrete address for ``self._method`` and
        requests an :class:`AddressChannel` from the parent :class:`Channel`.
        The returned :class:`grpc.aio.UnaryUnaryCall` has a done-callback
        attached that returns or discards the address channel back to the
        channel pool when the RPC completes.

        :param request: The protobuf request message to send.
        :param timeout: Optional per-call timeout in seconds.
        :param metadata: Optional gRPC metadata to send with the request.
        :param credentials: Optional per-call call-credentials.
        :param wait_for_ready: Optional gRPC wait_for_ready flag.
        :param compression: Optional gRPC compression setting.
        :return: A :class:`grpc.aio.UnaryUnaryCall` representing the in-flight
            RPC. The caller may await or add callbacks to the returned object.
        """

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
            """Callback executed when the RPC finishes.

            The callback returns or discards the address channel back to the
            channel pool. If the channel manager has already been closed it
            attempts a short synchronous close of the underlying channel.
            """
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
    """Marker type used to explicitly disable authorization.

    When this value is supplied as the ``credentials`` parameter to
    :class:`Channel`, the channel will not attempt to acquire or attach any
    authorization tokens for outgoing requests.
    """


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
    """Ensure the provided awaitable is a coroutine object.

    gRPC helper functions in this module accept both coroutine objects and
    other awaitable types (for example :class:`asyncio.Future`). This function
    normalizes them into a coroutine so that they can be wrapped in an
    :class:`asyncio.Task` safely.

    :param awaitable: Any awaitable or coroutine-like object.
    :return: A coroutine object ready to be scheduled.
    :raises TypeError: If the argument is not awaitable.
    """

    if iscoroutine(awaitable):
        return awaitable
    if not isawaitable(awaitable):
        raise TypeError(
            "An asyncio.Future, a coroutine or an awaitable is "
            + f"required, {type(awaitable)} given"
        )

    async def wrap() -> T:
        """Adapter coroutine that awaits the supplied awaitable and returns
        its result.

        This small wrapper is used to convert generic awaitable objects into
        a true coroutine so they can be scheduled as an :class:`asyncio.Task`.
        """
        return await awaitable

    return wrap()


async def _run_awaitable_with_timeout(
    f: Awaitable[T],
    timeout: float | None = None,
) -> T:
    """Run an awaitable with an optional wall-clock timeout.

    The function creates an :class:`asyncio.Task` from the provided awaitable
    and, if a timeout is supplied, a short timer task. It waits for the first
    task to finish. If the timer completes first the awaited task is
    cancelled and a :class:`TimeoutError` is raised. Exceptions raised by the
    awaited task are propagated.

    :param f: The awaitable to run.
    :param timeout: Optional timeout in seconds. If ``None`` the awaitable is
        allowed to run indefinitely.
    :return: The awaited result.
    :raises TimeoutError: If the awaitable did not finish before the timeout.
    """

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
    """
    Set or override the ``grpc.primary_user_agent`` channel option.
    This helper appends the provided user-agent string to the ``options``
    sequence, which is passed to gRPC when creating channels. If the
    ``grpc.primary_user_agent`` option is already present in ``options``,
    it will be replaced with the new value.

    :param user_agent: The user-agent string to set.
    :type user_agent: str
    :param options: Existing channel options, if any.
    :type options: optional list of ``(str, Any)`` tuples
    :return: The updated channel options including the user-agent.
    :rtype: list of ``(str, Any)`` tuples
    """
    options = list(options or [])
    options.append(("grpc.primary_user_agent", user_agent))
    return options


class Channel(ChannelBase):  # type: ignore[unused-ignore,misc]
    """A high-level gRPC channel manager used by the SDK.

    Responsibilities and behavior
    ==============================

    - Resolve service names to addresses and create underlying gRPC channels for
        those addresses.
    - Maintain a small pool of free channels per address to reuse connections and
        reduce churn (see ``max_free_channels_per_address`` init param).
    - Provide helpers to attach authorization credentials and manage token
        providers, including synchronous and asynchronous token acquisition via
        :meth:`get_token` and :meth:`get_token_sync`.
    - Expose convenience wrappers for unary-unary RPCs that ensure the address
        channel is returned to the pool when the RPC completes (see
        :class:`NebiusUnaryUnaryMultiCallable`).
    - Offer both async and sync usage models. Use the async context manager
        (``async with Channel(...)``) or call ``close()``/``sync_close()`` to
        gracefully shut down resources.

    Important notes
    ---------------

    - The channel owns a configurable asyncio event loop (optionally provided at
        construction). When calling ``run_sync`` from within an already running
        loop, a :class:`LoopError` is raised unless a separate loop was supplied at
        initialization.
    - The class cooperates with several SDK subsystems (token bearers,
        authorization providers, idempotency interceptor, and a resolver) and
        wires them together during initialization.
    - Public helper methods include: ``get_token``/``get_token_sync``,
        ``run_sync``, ``bg_task``, ``get_channel_by_method``, and
        ``create_address_channel``.

    Usage example
    =============

    Async usage (recommended)::

        async with Channel(...) as channel:
            # use channel or pass it to generated service clients
            pass

    Synchronous usage::

        channel = Channel(...)
        try:
            channel.run_sync(some_coroutine())
        finally:
            channel.sync_close()

    :ivar user_agent: The user-agent string used by channels created by
        this Channel instance.

    :param resolver:
        Optional custom :class:`Resolver` used to resolve service names to concrete
        addresses. If omitted a :class:`Conventional` resolver is used. If
        provided, it will be chained with the built-in resolver so both
        can be consulted.
    :type resolver: optional :class:`Resolver`

    :param substitutions:
        Optional mapping of template substitutions applied to resolved
        addresses. The construct inserts ``{"{domain}": domain}`` and
        then updates it with this mapping. Typical use is to override
        domain placeholders in generated service addresses.
    :type substitutions: optional dict[from, to]

    :param user_agent_prefix:
        Optional string prepended to the default SDK user-agent. The
        final user-agent string follows the pattern
        ``"<user_agent_prefix> nebius-python-sdk/<version> (python/X.Y.Z)"``.
        Recommended format:
        ``"my-app/1.0 (dependency-to-track/version; other-dependency)"``.
    :type user_agent_prefix: optional str

    :param domain:
        Optional domain to substitute into service addresses. When not
        provided the constructor will try to obtain it from the provided
        ``config_reader`` via ``config_reader.endpoint()``, and fall back
        to the package-level ``DOMAIN`` constant if still unset.
    :type domain: optional str

    :param options:
        Global channel options passed to gRPC when creating address
        channels. This should follow the ``ChannelArgumentType``
        shape (sequence of key/value tuples).
    :type options: optional list of tuple[str, Any]

    :param interceptors:
        Global list of gRPC :class:`ClientInterceptor`
        instances that will be applied to all address channels. An
        idempotency-key interceptor is added by default; pass a list to
        extend or override additional behavior.
    :type interceptors: optional list of :class:`ClientInterceptor`

    :param address_options:
        Optional mapping from a resolved address to per-address channel
        options. Each value must follow the ``ChannelArgumentType``
        shape (sequence of key/value tuples). If omitted
        an empty mapping is used.
    :type address_options: optional mapping address -> list of ``tuple[str, Any]``

    :param address_interceptors:
        Optional mapping from a resolved address to a sequence of
        per-address interceptors. Per-address interceptors are invoked
        in addition to the global interceptors.
    :type address_interceptors: optional mapping address ->
        Sequence[ClientInterceptor]

    :param credentials:
        Credentials can be provided in several forms:

        - ``None`` (default): attempts to read credentials from
            ``credentials_file_name``, then from provided service account
            fields, then from ``config_reader.get_credentials(...)``, and
            finally falls back to an environment-backed bearer
            (:class:`nebius.aio.token.static.EnvBearer`).
        - ``str`` or :class:`Token`: treated as a
            static token and wrapped with a static bearer.
        - :class:`TokenBearer` to use an existing token bearer as-is.
        - :class:`TokenRequester` to exchange tokens on demand.
        - :class:`AuthorizationProvider`: an explicit authorization provider
            (used rarely by advanced users).
        - :class:`NoCredentials`: disables authorization entirely.

        Unsupported types raise :class:`SDKError`.
    :type credentials: token in form of string or :class:`Token`, or classes
        :class:`TokenBearer`, :class:`TokenRequester`,
        :class:`AuthorizationProvider`, :class:`NoCredentials`

    :param service_account_id:
        Service account ID used when a private key file is supplied
        directly (alternate to using ``credentials_file_name``). See the
        README for examples. If ``credentials`` is provided explicitly
        this parameter is ignored.
    :type service_account_id: optional str

    :param service_account_public_key_id:
        Public key ID corresponding to the private key file used for
        service-account authentication, as described in the README. If
        ``credentials`` is provided explicitly this parameter is ignored.
    :type service_account_public_key_id: optional str

    :param service_account_private_key_file_name:
        Path to a PEM private key file. When provided with the key ID and service
        account ID fields above, the constructor wraps it in a service-account
        reader.
    :type service_account_private_key_file_name: optional str or :class:`Path`

    :param credentials_file_name:
        Path to a credentials JSON file containing service-account
        information. If supplied this takes precedence over other implicit
        credential discovery (unless ``credentials`` is explicitly
        provided).
    :type credentials_file_name: optional str or :class:`Path`

    :param config_reader:
        Optional :class:`nebius.aio.cli_config.Config` instance used to
        populate defaults like domain, default parent ID, and to obtain
        credentials via the CLI-style configuration.
    :type config_reader: optional :class:`ConfigReader`

    :param tls_credentials:
        Optional gRPC channel TLS credentials (:class:`ChannelCredentials`).
        If omitted the constructor will load system root certificates via
        :func:`nebius.base.tls_certificates.get_system_certificates` and
        create an SSL channel credentials object.
    :type tls_credentials: optional :class:`ChannelCredentials`

    :param event_loop:
        Optional asyncio event loop to be owned by this Channel. When a
        loop is provided, synchronous helpers such as :meth:`run_sync`
        may be called from other threads without raising
        :class:`LoopError`. If not provided the Channel will lazily
        create its own loop when a synchronous call is made.
    :type event_loop: optional :class:`AbstractEventLoop`

    :param max_free_channels_per_address:
        Number of free underlying gRPC channels to keep in the pool per
        resolved address. Defaults to 2. Lower values reduce resource
        usage but increase connection churn; larger values raise resource
        consumption.
    :type max_free_channels_per_address: optional int

    :param parent_id:
        Optional parent ID which will be automatically applied to many
        requests when left empty by the caller. If not provided and a
        ``config_reader`` is supplied the constructor will attempt to use
        ``config_reader.parent_id``. An explicit empty string is treated
        as an error.
    :type parent_id: optional str

    :param federation_invitation_writer:
        Optional file-like writer passed to the config reader to display
        the URL for federation authentication during interactive credential
        acquisition.
    :type federation_invitation_writer: optional :class:`TextIO`

    :param federation_invitation_no_browser_open:
        When using the config reader, set to ``True`` to avoid opening a web
        browser during interactive federation flows. Defaults to ``False``.
    :type federation_invitation_no_browser_open: optional bool
    """

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
        """
        Construct a new Channel instance.

        This constructor wires together the SDK's gRPC channel management,
        credential providers, resolvers, TLS configuration and interceptors.

        The Channel is responsible for resolving logical service names to
        transport addresses, creating and pooling underlying gRPC channels,
        and exposing helpers for synchronous and asynchronous usage.

        :raises SDKError:
            Raised for unsupported credential types or if ``parent_id`` is an
            explicitly empty string.

        Notes
        -----
        - The constructor performs several discovery steps for credentials in
          the following precedence order when ``credentials`` is ``None``:
          1. ``credentials_file_name`` reader
          2. service-account PEM reader (when id/key args are provided)
          3. ``config_reader.get_credentials(...)``
          4. environment-backed bearer (:class:`EnvBearer`)

        - Token readers are wrapped into exchangeable/renewable bearers so
          that token refresh happens transparently in the background and the
          Channel adds the bearer to its graceful shutdown set to ensure
          background tasks are cleaned up on :meth:`close`.

        Examples
        --------
        Typical, minimal construction that reads token from environment:

        >>> channel = Channel()

        Using explicit static token:

        >>> channel = Channel(credentials="MY_TOKEN")

        Creating channel from CLI config and a custom resolver:

        >>> from nebius.aio.cli_config import Config
        >>> channel = Channel(config_reader=Config(), resolver=my_resolver)

        """

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
        self._authorization_provider: AuthorizationProvider | None = None
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
            self._authorization_provider = credentials
        elif not isinstance(credentials, NoCredentials):  # type: ignore[unused-ignore]
            raise SDKError(f"credentials type is not supported: {type(credentials)}")

        self._event_loop = event_loop
        self._closed = False

    def get_authorization_provider(self) -> AuthorizationProvider | None:
        """Return the configured :class:`AuthorizationProvider`.

        :return: The authorization provider instance if any authorization
            mechanism was configured; otherwise ``None``.
        :rtype: :class:`AuthorizationProvider` or None
        """
        return self._authorization_provider

    async def get_token(
        self,
        timeout: float | None,
        options: dict[str, str] | None = None,
    ) -> Token:
        """Asynchronously fetch an authorization :class:`Token`.

        This helper delegates to the configured token bearer and performs any
        necessary refresh or exchange logic implemented by the bearer, if any was
        configured. If no bearer was configured, the method raises
        :class:`SDKError`.

        :param timeout: Maximum time in seconds to wait for a token. If
            ``None`` the operation may block indefinitely according to the
            bearer semantics.
        :type timeout: optional float
        :param options: Optional mapping of string options passed to the
            underlying token receiver.
        :type options: optional ``dict[str, str]``
        :return: A :class:`Token` instance containing the access token.
        :rtype: :class:`Token`
        :raises SDKError: If no token bearer was configured on the channel.
        """

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
        """Synchronously fetch an authorization :class:`Token`.

        This method is a convenience wrapper around :meth:`get_token` that
        runs the async fetch on the channel's owned event loop and blocks the
        calling thread until the token is available or the timeout expires.

        A small grace period is added to the supplied timeout to allow the
        internal token bearer shutdown logic to complete during immediate
        handoff.

        :param timeout: Maximum time in seconds to wait for a token; may be
            ``None`` to wait indefinitely.
        :type timeout: optional float
        :param options: Optional mapping of string options passed to the
            underlying token receiver.
        :type options: optional ``dict[str, str]``
        :return: A :class:`Token` instance.
        :rtype: :class:`Token`
        :raises TimeoutError: If the token could not be obtained within the
            supplied timeout.
        """

        timeout_sync = timeout
        if timeout_sync is not None:
            timeout_sync += 0.2  # 200 ms for graceful shutdown
        return self.run_sync(
            self.get_token(timeout, options),
            timeout_sync,
        )

    def parent_id(self) -> str | None:
        """Return the channel-wide default parent ID used for certain requests.

        Some SDK methods automatically populate a ``parent_id`` field when
        missing using this channel-level default. The value may be ``None`` if not
        configured.

        :return: The configured parent ID or ``None``.
        :rtype: str | None
        """

        return self._parent_id

    def bg_task(self, coro: Awaitable[T]) -> Task[None]:
        """Run a coroutine in the background and log uncaught exceptions.

        The returned task is automatically tracked by the channel and will be
        cancelled during :meth:`close`. Any non-cancellation exception is
        logged to the module logger.

        :param coro: An awaitable object to run in the background.
        :return: The created :class:`asyncio.Task`.
        """

        async def wrapper() -> None:
            """Internal runner that awaits the provided coroutine and logs
            uncaught exceptions.

            Cancellation errors are ignored since they are part of normal
            shutdown semantics.
            """
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
        """Run an awaitable to completion on the channel's event loop.

        This helper supports two usage patterns:

        - If the channel was initialized with an explicit event loop, the
          awaitable will be scheduled on that loop and this function may be
          safely called from another thread.
        - If the channel has no provided loop, an internal loop is created or
          reused and ``run_until_complete`` is used. Calling this from a
          running loop without providing a separate loop raises
          :class:`LoopError`.

        :param awaitable: The awaitable to run to completion.
        :param timeout: Optional wall-clock timeout in seconds. If provided
            and the awaitable does not complete within the timeout a
            :class:`TimeoutError` is raised.
        :type timeout: optional float
        :return: The awaitable's result.
        :raises LoopError: When called synchronously inside a running loop
            and no separate event loop was provided at construction.
        """

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
        """Synchronously close the channel and wait for graceful shutdown.

        This is a convenience wrapper around :meth:`close` that blocks until
        the shutdown completes or the optional timeout elapses.

        :param timeout: Optional timeout in seconds for the shutdown.
        :type timeout: optional float
        :raises TimeoutError: If the shutdown did not complete within the
            supplied timeout.
        """

        return self.run_sync(self.close(), timeout)

    async def close(self, grace: float | None = None) -> None:
        """Gracefully close the channel and all associated background work.

        The channel will stop handing out address channels and will attempt to
        close any pooled gRPC channels and all registered ``GracefulInterface``
        objects (for example token bearers). Background tasks started via
        :meth:`bg_task` are cancelled. Any exceptions raised during shutdown
        are logged.

        :param grace: Optional per-transport grace period passed to underlying
            channel close methods.
        :type grace: optional float
        """

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
        """Return an operations service stub for the same address as a
        generated service stub.

        Many long-running operations are associated with the service that
        initiated them. This helper resolves the service address for the
        provided generated stub class and returns an instantiated
        :class:`OperationServiceStub` bound to the transport channel for that address.

        :param service_stub_class: Generated gRPC service stub class (the SDK service
            descriptor type).
        :return: An operations service stub bound to the same backend used by
            the provided service.
        :rtype: :class:`OperationServiceStub`
        """

        addr = self.get_addr_from_stub(service_stub_class)
        chan = self.get_channel_by_addr(addr)
        return OperationServiceStub(chan)  # type: ignore[no-untyped-call]

    def get_corresponding_operation_service_alpha(
        self,
        service_stub_class: type[ServiceStub],
    ) -> OperationServiceStubDeprecated:
        """Compatibility helper returning the alpha-version operations
        service stub for the same address as a generated service stub.

        See :meth:`get_corresponding_operation_service` for details. This
        method returns the older alpha operations stub for callers that need
        to interoperate with legacy server implementations.
        """

        addr = self.get_addr_from_stub(service_stub_class)
        chan = self.get_channel_by_addr(addr)
        return OperationServiceStubDeprecated(chan)  # type: ignore[no-untyped-call]

    def get_addr_from_stub(self, service_stub_class: type[ServiceStub]) -> str:
        """Resolve the concrete address for a generated service stub class.

        :param service_stub_class: The generated gRPC stub class for a
            service.
        :return: The resolved address string used by the SDK to reach that
            service (for example ``'host:port'`` or a resolver template
            expanded value).
        :rtype: str
        """

        service = from_stub_class(service_stub_class)
        return self.get_addr_from_service_name(service)

    def get_addr_from_service_name(self, service_name: str) -> str:
        """Resolve a logical service name into a transport address.

        The method strips a leading dot (``"."``) if present and delegates
        to the configured :class:`Resolver`.

        :param service_name: Logical service name as generated by stubs or
            conventions.
        :return: Resolved address string.
        :rtype: str
        """

        if len(service_name) > 1 and service_name[0] == ".":
            service_name = service_name[1:]
        return self._resolver.resolve(service_name)

    def get_addr_by_method(self, method_name: str) -> str:
        """Return the cached address for a fully-qualified RPC method name.

        If the method-to-service mapping has not been seen before it is
        computed using :func:`service_from_method_name`
        and resolved via :meth:`get_addr_from_service_name`. The result is
        cached to accelerate future lookups.

        :param method_name: Full RPC method string (``'/package.service/Method'``).
        :return: Resolved address string.
        :rtype: str
        """

        if method_name not in self._methods:
            service_name = service_from_method_name(method_name)
            self._methods[method_name] = self.get_addr_from_service_name(service_name)
        return self._methods[method_name]

    def get_channel_by_addr(self, addr: str) -> AddressChannel:
        """Request an :class:`AddressChannel` for the given resolved address.

        The method returns a pooled channel if available; otherwise a new
        underlying gRPC channel is created. Pooled channels with state
        :attr:`grpc.ChannelConnectivity.SHUTDOWN` are closed asynchronously and
        skipped.

        :param addr: Resolved address string.
        :return: An :class:`AddressChannel` wrapper for a gRPC channel.
        :rtype: :class:`AddressChannel`
        :raises ChannelClosedError: If the SDK channel has already been closed.
        """

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
        """Return an :class:`AddressChannel` to the internal pool.

        Channels returned to the pool will be reused by subsequent
        :meth:`get_channel_by_addr` calls up to the configured
        ``max_free_channels_per_address`` limit. Channels that are shut down
        or exceed the pool size are closed asynchronously.

        :param chan: The :class:`AddressChannel` to return, or ``None``.
        :raises ChannelClosedError: If the SDK channel has been closed.
        """

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
        """Dispose of an :class:`AddressChannel` by scheduling its close.

        The close is performed asynchronously via :meth:`bg_task` to avoid
        blocking the caller.

        :param chan: The :class:`AddressChannel` to discard, or ``None``.
        :raises ChannelClosedError: If the SDK channel has been closed.
        """

        if chan is None:
            return
        if self._closed:
            raise ChannelClosedError("Channel closed")
        self.bg_task(chan.channel.close(None))

    def get_channel_by_method(self, method_name: str) -> AddressChannel:
        """Convenience to obtain an :class:`AddressChannel` for an RPC
        method name.
        The method resolves the address via :meth:`get_addr_by_method` and
        then calls :meth:`get_channel_by_addr` to obtain the channel.

        :param method_name: Full RPC method string.
        :return: An :class:`AddressChannel` bound to the resolved address.
        """

        addr = self.get_addr_by_method(method_name)
        return self.get_channel_by_addr(addr)

    def get_address_options(self, addr: str) -> ChannelArgumentType:
        """Compute effective gRPC channel options for a specific address.

        Global options are combined with per-address options and the SDK
        user-agent is appended via ``grpc.primary_user_agent``.

        :param addr: Resolved address string.
        :return: A sequence of channel option tuples ready to be passed to
            gRPC when creating a channel.
        :rtype: list of ``tuple[str, Any]``
        """

        ret = [opt for opt in self._global_options]
        if addr in self._address_options:
            ret.extend(self._address_options[addr])
        ret = set_user_agent_option(self.user_agent, ret)  # type: ignore[assignment]
        return ret

    def get_address_interceptors(self, addr: str) -> Sequence[ClientInterceptor]:
        """Return the ordered list of interceptors to apply to a channel.

        Global interceptors are applied first, then any per-address
        interceptors, and finally internal interceptors added by the
        channel implementation.

        :param addr: Resolved address string.
        :return: Combined global and per-address interceptors.
        :rtype: A sequence of :class:`ClientInterceptor`
        """

        ret = [opt for opt in self._global_interceptors]
        if addr in self._address_interceptors:
            ret.extend(self._address_interceptors[addr])
        ret.extend(self._global_interceptors_inner)
        return ret

    def create_address_channel(self, addr: str) -> AddressChannel:
        """Create a new underlying gRPC channel for the given address.

        The method composes options and interceptors, extracts known
        special options such as ``INSECURE`` and ``COMPRESSION``, and then
        constructs either a secure or insecure gRPC channel wrapper. The
        returned object is an :class:`AddressChannel` that pairs the gRPC
        channel with the resolved address string.

        :param addr: Resolved address string.
        :type addr: str
        :return: An :class:`AddressChannel` containing the created channel.
        :rtype: :class:`AddressChannel`
        """

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
        """
        A method to support using SDK channel as gRPC Channel.

        :param method_name:
            Full RPC method string, i.e., ``'/package.service/method'``.
        :type method_name: str
        :param request_serializer:
            A function that serializes a request message to bytes.
        :type request_serializer: SerializingFunction | None
        :param response_deserializer:
            A function that deserializes a response message from bytes.
        :type response_deserializer: DeserializingFunction | None
        :return:
            A :class:`UnaryUnaryMultiCallable` object that can be used to make
            the call.
        :rtype: :class:`NebiusUnaryUnaryMultiCallable` wrapper.
        """
        return NebiusUnaryUnaryMultiCallable(
            self,
            method_name,
            request_serializer,
            response_deserializer,
        )

    async def __aenter__(self) -> "Channel":
        """
        Enter the async context manager.
        Returns self to allow usage like::

            async with channel as chan:
                await chan.some_method()

        Will close the channel on exit.
        """
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exit the async context manager.
        Calls close() to gracefully shut down resources.
        """
        await self.close(None)

    def get_state(self, try_to_connect: bool = False) -> ChannelConnectivity:
        """
        Nebius Python SDK channels are always ready unless closed.

        :param try_to_connect:
            Ignored parameter to satisfy the gRPC Channel interface.
        :type try_to_connect: bool
        :return:
            :attr:`grpc.ChannelConnectivity.READY` if the channel is open,
            :attr:`grpc.ChannelConnectivity.SHUTDOWN` if closed.
        :rtype: :class:`grpc.ChannelConnectivity`
        """
        if self._closed:
            return ChannelConnectivity.SHUTDOWN
        return ChannelConnectivity.READY

    async def wait_for_state_change(
        self,
        last_observed_state: ChannelConnectivity,
    ) -> None:
        """
        Nebius Python SDK channels are always ready unless closed.
        This method is provided to satisfy the gRPC Channel interface.

        :raises NotImplementedError:
        """
        raise NotImplementedError("this method has no meaning for this channel")

    async def channel_ready(self) -> None:
        """
        Channel is always ready, nothing to do here.
        """
        return

    def unary_stream(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> UnaryStreamMultiCallable[Req, Res]:  # type: ignore[unused-ignore]
        """
        Nebius Python SDK does not support streaming RPCs.

        :raises NotImplementedError:
        """
        raise NotImplementedError("Method not implemented")

    def stream_unary(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> StreamUnaryMultiCallable:
        """
        Nebius Python SDK does not support streaming RPCs.

        :raises NotImplementedError:
        """
        raise NotImplementedError("Method not implemented")

    def stream_stream(  # type: ignore[unused-ignore,override]
        self,
        method: str,
        request_serializer: SerializingFunction | None = None,
        response_deserializer: DeserializingFunction | None = None,
    ) -> StreamStreamMultiCallable:
        """
        Nebius Python SDK does not support streaming RPCs.

        :raises NotImplementedError:
        """
        raise NotImplementedError("Method not implemented")
