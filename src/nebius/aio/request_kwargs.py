"""Define keyword arguments that apply to all SDK requests.

Usage::

    from nebius.aio.request_kwargs import RequestKwargs
    from typing_extensions import Unpack  # or from typing import Unpack in Python 3.11+
    from nebius.api.nebius... import SomeService, SomeRequest # illustrative only

    def my_request_wrapper(some_arg, **kwargs: Unpack[RequestKwargs]):
        request = SomeRequest(arg=some_arg) # build your request here

        return SomeService(sdk).some_method( # initialize your service client
            request,
            **kwargs, # pass the request kwargs along with the service call
        )

    result = await my_request_wrapper(
        some_arg="value",
        timeout=5.0,
        retries=2,
    )
"""

from collections.abc import Iterable
from typing import TypedDict

from grpc import CallCredentials, Compression

from nebius.aio.base import AddressChannel
from nebius.base.protos.unset import UnsetType


class StreamRequestKwargs(TypedDict, total=False):
    """Keyword arguments accepted by native streaming RPC requests."""

    metadata: Iterable[tuple[str, str]] | None
    timeout: float | None
    auth_timeout: float | None
    auth_options: dict[str, str] | None
    credentials: CallCredentials | None
    compression: Compression | None
    wait_for_ready: bool | None
    grpc_channel_override: AddressChannel | None


class RequestKwargsForOperation(TypedDict, total=False):
    """Define common keyword arguments for requests and operation waits.

    Operation waits replace or rename some :class:`RequestKwargs` parameters.
    See that class for the complete parameter set.

    :ivar metadata: Optional initial gRPC metadata to attach to the call.
    :type metadata: either :class:`nebius.base.metadata.Metadata`
        or list of ``(str, str)`` tuples.

    :ivar auth_timeout: Maximum time in seconds for authorization and request
        execution. The total time does not exceed this value.
        Default is :data:`nebius.aio.request.DEFAULT_AUTH_TIMEOUT`.
        Set ``None`` for no timeout.
    :type auth_timeout: optional ``float`` or ``None``

    :ivar auth_options: Optional dictionary that the request gives to the
        authenticator. See the authenticator documentation for
        provider-specific keys.
    :type auth_options: optional ``dict[str, str]``

    :ivar credentials: Optional gRPC :class:`CallCredentials` for the RPC.
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
    """Define common keyword arguments for all requests.

    :ivar timeout: Maximum time in seconds for request execution.
        Set ``None`` for no timeout.
        Default is :data:`nebius.aio.request.DEFAULT_TIMEOUT`.
    :type timeout: optional ``float`` or ``None``

    :ivar retries: Number of retry attempts after temporary failures.
        The default value is 3.
    :type retries: optional ``int`` or ``None``

    :ivar per_retry_timeout: Maximum time in seconds for each retry attempt.
        Set ``None`` for no timeout. The default value is
        :data:`nebius.aio.request.DEFAULT_PER_RETRY_TIMEOUT`.
    :type per_retry_timeout: optional ``float`` or ``None``
    """

    timeout: float | None | UnsetType
    retries: int | None
    per_retry_timeout: float | None | UnsetType

    # When adding new fields, consider adding them to RequestKwargsForOperation instead.
