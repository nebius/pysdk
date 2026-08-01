"""High-level interface for Nebius services."""

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
    """Provide a high-level interface for Nebius services.

    The SDK is a small wrapper for a gRPC channel. It supplies high-level
    methods, such as a method to get the authenticated profile. It inherits
    channel functions such as resolution, pooling, credential configuration,
    and synchronous and asynchronous calls.

    Quick start -- initialization
    =============================

    These examples show common SDK configurations. Replace
    ``example-application/1.0`` with your application name and version.

    - From an IAM token in the environment (default behavior)::

        sdk = SDK(user_agent_prefix="example-application/1.0")

    - With an explicit token string or static bearer::

        sdk = SDK(
            credentials="MY_IAM_TOKEN",
            user_agent_prefix="example-application/1.0",
        )
        # or
        sdk = SDK(
            credentials=Bearer("MY_IAM_TOKEN"),
            user_agent_prefix="example-application/1.0",
        )

    - From an env-backed token provider::

        from nebius.aio.token.static import EnvBearer
        sdk = SDK(
            credentials=EnvBearer("NEBIUS_IAM_TOKEN"),
            user_agent_prefix="example-application/1.0",
        )

    - From the CLI config reader (reads endpoints/profile like the CLI)::

        from nebius.aio.cli_config import Config
        sdk = SDK(
            config_reader=Config(),
            user_agent_prefix="example-application/1.0",
        )

    - Service account private key or credentials file::

        sdk = SDK(
            service_account_private_key_file_name="private.pem",
            service_account_public_key_id="pub-id",
            service_account_id="service-account-id",
            user_agent_prefix="example-application/1.0",
        )
        # or
        sdk = SDK(
            credentials_file_name="path/to/credentials.json",
            user_agent_prefix="example-application/1.0",
        )

    Async vs sync usage and lifecycle
    ---------------------------------

    The SDK is designed for asyncio. The asynchronous context manager stops
    background tasks correctly::

        async with SDK(
            ...,
            user_agent_prefix="example-application/1.0",
        ) as sdk:
            resp = await sdk.whoami()

    Each SDK owns a separate daemon event-loop thread and a private daemon
    executor by default. Its awaitable handles may be awaited from any asyncio
    loop. Synchronous helpers remain invalid inside an active async call stack;
    await the handle there. Use synchronous helpers from regular threads::

          sdk = SDK(
              ...,
              user_agent_prefix="example-application/1.0",
          )
          try:
              resp = sdk.whoami().wait()
          finally:
              sdk.sync_close()

    To use a caller-owned loop, pass an already-running ``event_loop``. Closing
    the SDK does not stop or reconfigure a supplied loop or its default
    executor. Do not fill that executor with synchronous SDK waits: custom SDK
    work on the supplied loop may need an executor worker, and the SDK cannot
    reliably identify threads owned by an arbitrary caller executor.

    Authentication and ``auth_timeout``
    -----------------------------------

    - ``auth_timeout`` limits credential acquisition, credential renewal, and
      the request. Many calls accept this parameter.
    - The default is 15 minutes (900 seconds). Set ``auth_timeout=None`` to
      remove the limit. Authentication can then wait indefinitely.
    - Use ``auth_options`` to control renewal. For example, make renewal
      synchronous or return renewal errors as request errors.

    Timeouts and retries (summary)
    ------------------------------

    - The overall timeout limits the request and all retries.
    - The per-retry timeout limits each retry attempt.
    - The default overall timeout is 60 seconds.
    - The default per-retry timeout is 20 seconds (60 seconds / 3 retries).
    - Set ``timeout=None`` to disable the request deadline.
    - Set ``retries`` and ``per_retry_timeout`` for each call as necessary.

    Keepalive
    ---------

    - By default, SDK channels use gRPC keepalive settings that are compatible
      with the Nebius SDK for Go.
    - The SDK reads the ``NEBIUS_GRPC_KEEPALIVE_*`` environment variables.
    - Set ``keepalive=False`` to disable SDK keepalive.
    - To change the settings, give
      :class:`nebius.aio.keepalive.KeepaliveOptions` or a mapping. The mapping
      can contain ``time_ms``, ``timeout_ms``, and ``permit_without_stream``.
    - gRPC options in ``options`` or ``address_options`` apply later. These
      options can replace individual keepalive arguments.

    Metrics
    -------

    - Give ``metrics`` to receive configuration-reader and authentication
      events.
    - Give ``auth_metrics`` to receive only authentication events.
    - If you give ``metrics``, the SDK uses it for authentication callbacks
      and ignores ``auth_metrics``.
    - A metric sink can be an object with callback methods. It can also be a
      mapping of callback names to functions.
    - Callback names can use Python snake_case or TypeScript-style camelCase.
    - ``callback_timeout_seconds`` limits awaitable callback results. The SDK
      adjusts invalid or too-large values to its limits.
    - The SDK ignores callback failures. Metrics do not affect SDK requests.

    Parent ID auto-population
    -------------------------

    - The SDK can set ``parent_id`` automatically for applicable methods. It
      gets the value from :class:`nebius.aio.cli_config.Config` or the SDK
      ``parent_id`` initialization parameter.
    - To use the CLI configuration without its parent ID, set
      ``no_parent_id=True``.

    Operations
    ----------

    - Long-running service calls return an
      :class:`nebius.aio.operation.Operation` wrapper. You can await this
      wrapper until the operation is complete.
    - Use the source service's ``operation_service()`` method to list
      operations.
    - The ``Operation`` wrapper supplies ``.wait()`` and ``.resource_id``.

    Request metadata and debugging
    ------------------------------

    - Service methods return :class:`Request` objects. These objects supply
      metadata such as the request ID and trace ID.
    - You can await a request or wait for it synchronously.
    - Example::

        request = sdk.whoami()  # Do not await the request yet.
        resp = await request
        request_id = await request.request_id()
        trace_id = await request.trace_id()

    Error handling and :class:`nebius.aio.service_error.RequestError`
    -----------------------------------------------------------------

    - Server errors derive from
      :class:`nebius.aio.service_error.RequestError`.
    - Catch the error and read ``err.status`` for structured server details.

    User-agent customization
    ------------------------

    - Set ``user_agent_prefix`` when you construct the SDK.
    - You can also set ``grpc.primary_user_agent`` in ``options``.
    - The SDK combines these values with its internal version string.

    See also
    --------

    - See the project README and API reference for more examples and
      explanations.
    """

    def whoami(
        self,
        **kwargs: Unpack[RequestKwargs],
    ) -> Request[GetProfileRequest, GetProfileResponse]:
        """Return a request to get the profile for the current credentials.

        This method wraps the generated :class:`ProfileServiceClient.get`
        method.

        Give request arguments as keyword arguments.
        See :class:`nebius.aio.request_kwargs.RequestKwargs` for details.

        :return: A :class:`Request` for the active RPC. Await it or use its
            ``.wait()`` methods.
        :rtype: :class:`Request` of
            :class:`GetProfileResponse`
        """

        client = ProfileServiceClient(self)
        return client.get(
            GetProfileRequest(),
            **kwargs,
        )
