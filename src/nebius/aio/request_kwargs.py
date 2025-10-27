from collections.abc import Iterable
from typing import TypedDict

from grpc import CallCredentials, Compression

from nebius.base.protos.unset import UnsetType


class RequestKwargsForOperation(TypedDict, total=False):
    """Encapsulates the general keyword arguments for operation wait requests, without
    overridden parameters.

    :ivar metadata: Optional initial gRPC metadata to attach to the call.
    :type metadata: either :class:`nebius.base.metadata.Metadata`
        or list of ``(str, str)`` tuples.

    :ivar auth_timeout: Timeout budget (seconds) reserved for authorization
        flows plus the request execution. When provided the total authorization
        + request time will not exceed this value.
        Default is :data:`nebius.aio.request.DEFAULT_AUTH_TIMEOUT`.
        Provide `None` for infinite timeout.
    :type auth_timeout: optional `float` or `None`

    :ivar auth_options: Optional dictionary forwarded to the authenticator
        when performing authorization. See the authenticator documentation for
        provider-specific keys.
    :type auth_options: optional ``dict[str, str]``

    :ivar credentials: Optional gRPC :class:`CallCredentials` to use for the
        RPC invocation.
    :type credentials: optional :class:`grpc.CallCredentials`

    :ivar compression: Optional gRPC compression setting for the RPC.
    :type compression: optional :class:`grpc.Compression`
    """

    metadata: Iterable[tuple[str, str]] | None
    auth_timeout: float | None | UnsetType
    auth_options: dict[str, str] | None
    credentials: CallCredentials | None
    compression: Compression | None


class RequestKwargs(RequestKwargsForOperation, total=False):
    """Encapsulates the general keyword arguments for any request.

    :ivar timeout: Overall timeout (seconds) applied to the request execution
        portion. Or `None` for infinite timeout.
        Default is :data:`nebius.aio.request.DEFAULT_TIMEOUT`.
    :type timeout: optional `float` or `None`

    :ivar retries: Number of retry attempts for transient failures. Default is 3.
    :type retries: optional `int` or `None`

    :ivar per_retry_timeout: Timeout (seconds) applied to each retry attempt
        individually. You can pass `None` for infinite timeout. Default is
        :data:`nebius.aio.request.DEFAULT_PER_RETRY_TIMEOUT`.
    :type per_retry_timeout: optional `float` or `None`
    """

    timeout: float | None | UnsetType
    retries: int | None
    per_retry_timeout: float | None | UnsetType
