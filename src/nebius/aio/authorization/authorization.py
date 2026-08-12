"""Authorization interfaces used by the async SDK.

This module defines two abstract interfaces used by the SDK to perform
request-time authorization.

Typical usage within the request lifecycle
------------------------------------------

Give a :class:`Provider` to the request constructor. Before it sends an RPC,
the request layer calls :meth:`Provider.authenticator` to get an
:class:`Authenticator`.

The authenticator authorizes one request. It adds the required headers to
:class:`nebius.base.metadata.Metadata`. For example, it can add an
authorization bearer token. After an authentication failure, the request
layer calls :meth:`Authenticator.can_retry`. If permitted, it retries with
the same authenticator.
"""

from abc import ABC, abstractmethod

from nebius.base.metadata import Metadata


class Authenticator(ABC):
    """Abstract interface for performing per-request authentication.

    Subclasses must implement :meth:`authenticate`. They can implement
    :meth:`can_retry` to permit retries after authentication failures. For
    example, permit fewer than three retries after an ``UNAUTHENTICATED`` code.

    The built-in channel calls authenticators on its internal SDK event loop.
    A custom authenticator must be thread-safe and loop-neutral. It must not
    retain asyncio state that belongs to an application loop. Thread-local
    state does not move to the SDK thread; use :class:`contextvars.ContextVar`
    when context propagation is required.
    """

    @abstractmethod
    async def authenticate(
        self,
        metadata: Metadata,
        timeout: float | None = None,
        options: dict[str, str] | None = None,
    ) -> None:
        """Authenticate by modifying the ``metadata`` before sending an RPC.

        :param metadata: The metadata mapping that will be sent with the RPC.
            Implementations may mutate this mapping in-place to add or update
            authentication headers (for example the Authorization header).
        :type metadata: :class:`nebius.base.metadata.Metadata`
        :param timeout: Optional authentication timeout in seconds. Implementations
            must not exceed this timeout during the whole authentication process.
        :type timeout: optional `float`
        :param options: Optional, implementation-specific options passed from
            the request layer.
        :type options: optional ``dict[str, str]``
        """
        raise NotImplementedError("Method not implemented!")

    @abstractmethod
    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Return whether to call :meth:`authenticate` and retry.

        :param err: The exception raised during authentication or while the
            RPC was in-flight. Implementations inspect the exception to
            determine if a retry (for example after refreshing a token) is
            likely to succeed.
        :type err: :class:`Exception`
        :param options: Optional implementation-specific options.
        :type options: optional ``dict[str, str]``
        :returns: ``True`` when the authentication should be retried, otherwise
            ``False``.
        :rtype: bool
        """
        return False


class Provider(ABC):
    """Factory abstraction that supplies an :class:`Authenticator`.

    Typical usage within the request lifecycle
    ------------------------------------------

    Give a provider to the request constructor. Before it sends an RPC, the
    request layer calls :meth:`authenticator` to get an
    :class:`Authenticator`.

    The authenticator authorizes one request. It adds the required headers to
    :class:`nebius.base.metadata.Metadata`. After an authentication failure,
    the request layer calls :meth:`Authenticator.can_retry`. If permitted, it
    retries with the same authenticator.

    The built-in channel calls the provider and its authenticators on one SDK
    event loop. Treat a stateful provider as owned by one SDK. Do not attach
    one instance to SDKs with different loops unless the implementation is
    thread-safe, loop-neutral, and explicitly supports concurrent use.

    Example
    -------
    Give a provider to the SDK through the ``credentials`` parameter::

        from nebius.sdk import SDK
        from nebius.aio.authorization import Authenticator, Provider

        class MyAuthenticator(Authenticator):
            async def authenticate(self, metadata, timeout=None, options=None):
                metadata.add("Authorization", "Bearer my-static-token")

        class MyProvider(Provider):
            def authenticator(self):
                return MyAuthenticator()

        provider = MyProvider()
        sdk = SDK(
            credentials=provider,
            user_agent_prefix="example-application/1.0",
        )

    """

    @abstractmethod
    def authenticator(self) -> Authenticator:
        """Return a fresh per-request :class:`Authenticator` instance.

        :returns: An authenticator instance.
        """
        raise NotImplementedError("Method not implemented!")
