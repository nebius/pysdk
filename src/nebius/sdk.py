from typing_extensions import Unpack

from nebius.aio.channel import Channel
from nebius.aio.request import Request
from nebius.aio.request_kwargs import RequestKwargs
from nebius.api.nebius.iam.v1 import (
    GetProfileRequest,
    GetProfileResponse,
    ProfileServiceClient,
)


class SDK(Channel):
    """High-level SDK facade providing convenience helpers for Nebius services.

    The SDK class is a thin convenience wrapper around a gRPC channel that
    exposes higher-level helpers for common operations such as retrieving the
    current authenticated profile. It inherits from :class:`Channel`
    and therefore also exposes the channel-level behaviors and helpers
    (resolution, pooling, credential wiring, sync/async helpers).

    Quick start -- initialization
    =============================

    Common ways to construct the SDK:

    - From an IAM token in the environment (default behavior)::

        sdk = SDK()

    - With an explicit token string or static bearer::

        sdk = SDK(credentials="MY_IAM_TOKEN")
        # or
        sdk = SDK(credentials=Bearer("MY_IAM_TOKEN"))

    - From an env-backed token provider::

        from nebius.aio.token.static import EnvBearer
        sdk = SDK(credentials=EnvBearer("NEBIUS_IAM_TOKEN"))

    - From the CLI config reader (reads endpoints/profile like the CLI)::

        from nebius.aio.cli_config import Config
        sdk = SDK(config_reader=Config())

    - Service account private key or credentials file::

        sdk = SDK(service_account_private_key_file_name="private.pem",
                service_account_public_key_id="pub-id",
                service_account_id="service-account-id")
        # or
        sdk = SDK(credentials_file_name="path/to/credentials.json")

    Async vs sync usage and lifecycle
    ---------------------------------

    The SDK is designed for asyncio. Prefer the async context manager which
    ensures graceful shutdown of background tasks::

        async with SDK(...) as sdk:
            resp = await sdk.whoami()

    Synchronous usage is supported but riskier. It may raise
    :class:`nebius.aio.channel.LoopError` if used inside an active loop. For
    sync use::

          sdk = SDK(...)
          try:
              resp = sdk.whoami().wait()
          finally:
              sdk.sync_close()

    If you provide a separate event loop at construction you can safely call
    synchronous helpers from threads; otherwise avoid mixing sync calls with
    a running event loop.

    Authentication and ``auth_timeout``
    -----------------------------------

    - Many calls accept an ``auth_timeout`` parameter which bounds the total
      time spent acquiring or renewing credentials plus the enclosed request.
    - Default: 15 minutes (900 seconds). Pass ``auth_timeout=None`` to disable
      the bound (be cautious -- this can hang indefinitely if auth cannot
      complete).
    - ``auth_options`` may be provided to control renewal behavior (for example
      to make token renewal synchronous or to surface renewal errors as request
      errors).

    Timeouts and retries (summary)
    ------------------------------

    - The SDK uses two timeout levels:
        * overall request timeout (deadline for entire request including retries),
        * per-retry timeout (deadline for each individual retry attempt).
    - Defaults used by the SDK (unless overridden by a call):
        * overall request timeout: 60s
        * per-retry timeout: 20s (derived from 60s / 3 retries)
    - Set ``timeout=None`` to disable the request deadline.
    - Configure ``retries`` and ``per_retry_timeout`` per-call when needed.

    Parent ID auto-population
    -------------------------

    - Some methods (``list``, ``get_by_name``, ``get``, many others) may have
      a ``parent_id`` automatically populated from CLI
      :class:`nebius.aio.cli_config.Config` or the SDK ``parent_id`` provided at
      initialization.
    - To disable automatic parent population while retaining CLI config use the
      Config option ``no_parent_id=True``.

    Operations
    ----------

    - Long-running operations returned by service ``create``/``update`` or other calls
      are represented by an :class:`nebius.aio.operation.Operation` wrapper that can be
      awaited until completion. You can also list operations via the source service's
      ``operation_service()`` helper.
    - The ``Operation`` wrapper provides convenience helpers like ``.wait()`` and
      ``.resource_id``.

    Request metadata and debugging
    ------------------------------

    - Service methods return :class:`Request` objects. These provide access to
      additional metadata (request id, trace id) and can be awaited or waited on
      synchronously.
    - Example::

        request = sdk.whoami()   # does not await immediately
        resp = await request
        request_id = await request.request_id()
        trace_id = await request.trace_id()

    Error handling and :class:`nebius.aio.service_error.RequestError`
    -----------------------------------------------------------------

    - Server-created errors derive from :class:`nebius.aio.service_error.RequestError`
      and include structured information. Catch and inspect ``err.status`` for
      the server-provided details.

    User-agent customization
    ------------------------

    - Add custom user-agent parts via ``options`` (``grpc.primary_user_agent``)
      or the ``user_agent_prefix`` parameter when constructing the SDK. The SDK
      composes the final user-agent from these pieces and the internal SDK
      version string.

    See also
    --------

    - Full usage examples and deeper explanations are available in the
      project README and the API reference documentation.
    """

    def whoami(
        self,
        **kwargs: Unpack[RequestKwargs],
    ) -> Request[GetProfileRequest, GetProfileResponse]:
        """Return a request that fetches the profile for the current credentials.

        This is a convenience wrapper around the generated
        :class:`ProfileServiceClient.get` method.

        Request arguments may be provided as keyword arguments.
        See :class:`nebius.aio.request_kwargs.RequestKwargs` for details.

        :return: A :class:`Request` object representing the
            in-flight RPC. It can be awaited (async) or waited
            synchronously using its ``.wait()`` helpers.
        :rtype: :class:`Request` of
            :class:`GetProfileResponse`
        """

        client = ProfileServiceClient(self)
        return client.get(
            GetProfileRequest(),
            **kwargs,
        )
