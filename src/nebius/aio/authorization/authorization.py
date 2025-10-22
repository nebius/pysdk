"""Authorization interfaces used by the async SDK.

This module defines two abstract interfaces used by the SDK to perform
request-time authorization.

Typical usage within the request lifecycle
------------------------------------------

The :class:`Provider` is the object passed to request constructors and prior to sending
an RPC the request layer calls :meth:`Provider.authenticator()` to obtain an
:class:`Authenticator`.

The :class:`Authenticator` instance returned by the provider is treated as a
per-request authorizer: it is responsible for ensuring the
provided :class:`nebius.base.metadata.Metadata` contains the headers needed
for that request only (for example an Authorization bearer token). If
an authentication-related failure occurs, the request layer will consult
``Authenticator.can_retry`` and will retry with the same authenticator.
"""

from abc import ABC, abstractmethod

from nebius.base.metadata import Metadata


class Authenticator(ABC):
    """Abstract interface for performing per-request authentication.

    Subclasses must implement :meth:`authenticate` and may implement
    :meth:`can_retry` to indicate whether authentication failures should be
    retried, eg code UNAUTHENTICATED and number of calls to :meth:`authenticate` < 3.
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
        """Indicate whether a failed authentication attempt or failed request may be
        retried with a fresh authentication, calling to :meth:`authenticate`.

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

    The :class:`Provider` is the object passed to request constructors and prior to
    sending an RPC the request layer calls :meth:`Provider.authenticator()` to obtain an
    :class:`Authenticator`.

    The :class:`Authenticator` instance returned by the provider is treated as a
    per-request authorizer: it is responsible for ensuring the
    provided :class:`nebius.base.metadata.Metadata` contains the headers needed
    for that request only (for example an Authorization bearer token). If
    an authentication-related failure occurs, the request layer will consult
    ``Authenticator.can_retry`` and will retry with the same authenticator.

    Example
    -------

    A minimal example showing how a provider might be passed into an SDK or
    request layer. The actual SDK in this repo accepts a provider via the
    ``credentials`` parameter; the example below demonstrates the intent and
    typical usage::

        from nebius.sdk import SDK
        from nebius.aio.authorization import Authenticator, Provider

        class MyAuthenticator(Authenticator):
            async def authenticate(self, metadata, timeout=None, options=None):
                metadata.add("Authorization", "Bearer my-static-token")

        class MyProvider(Provider):
            def authenticator(self):
                return MyAuthenticator()

        provider = MyProvider()
        sdk = SDK(credentials=provider)  # SDK initialisation (illustrative)

    """

    @abstractmethod
    def authenticator(self) -> Authenticator:
        """Return a fresh per-request :class:`Authenticator` instance.

        :returns: An authenticator instance.
        """
        raise NotImplementedError("Method not implemented!")
