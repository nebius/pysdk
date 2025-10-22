"""Token-based authenticators and providers.

This module provides a small concrete implementation of the
authorization interfaces that fetches bearer tokens from a token provider
and injects them into request metadata.
"""

from nebius.base.metadata import Metadata

from ..token import token
from .authorization import Authenticator, Provider

HEADER = "authorization"
"""The metadata header used for the bearer token (``"authorization"``).
"""


class TokenAuthenticator(Authenticator):
    """Per-request authenticator that injects a bearer token.

    The authenticator uses a :class:`token.Receiver` to fetch a token which
    is then written into the request metadata under the header named by
    :data:`HEADER` as ``Bearer <token>``. The instance holds a reference to
    the receiver and delegates retry decisions to the receiver via
    :meth:`token.Receiver.can_retry`.

    :param receiver: Token receiver used to fetch tokens for each request.
    :type receiver: :class:`token.Receiver`
    """

    def __init__(self, receiver: token.Receiver) -> None:
        """Create a token authenticator."""
        super().__init__()
        self._receiver = receiver

    async def authenticate(
        self,
        metadata: Metadata,
        timeout: float | None = None,
        options: dict[str, str] | None = None,
    ) -> None:
        """Fetch a token from the receiver and set the ``authorization`` metadata
        header.

        The header is replaced (any existing value is removed) with a
        ``Bearer <token>`` value fetched from the receiver.

        :param metadata: Metadata mapping sent with the request; mutated in
            place to include the Authorization header.
        :type metadata: :class:`nebius.base.metadata.Metadata`
        :param timeout: Optional timeout for the token fetch operation.
        :type timeout: optional `float`
        :param options: Optional provider/request options passed through.
        :type options: optional ``dict[str, str]``
        """
        tok = await self._receiver.fetch(timeout=timeout, options=options)
        del metadata[HEADER]
        metadata.add(HEADER, f"Bearer {tok.token}")

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Delegate retry decision to the underlying token receiver.

        :param err: The exception that caused the request/authentication
            to fail.
        :type err: :class:`Exception`
        :param options: Optional provider/request options.
        :type options: optional ``dict[str, str]``
        :returns: `True` when the receiver indicates the operation should be
            retried (for example token refresh may succeed); `False` otherwise.
        :rtype: bool
        """
        return self._receiver.can_retry(err, options)


class TokenProvider(Provider):
    """Provider that builds :class:`TokenAuthenticator` instances.

    The provider owns a :class:`token.Bearer` and returns a fresh
    :class:`TokenAuthenticator` for each call to :meth:`authenticator`.

    :param token_provider: The bearer token provider used to obtain
        receivers for per-request authenticators.
    :type token_provider: :class:`token.Bearer`

    Example
    -------

    Construct a bearer-backed provider and (illustratively) pass it to the
    SDK via the credentials parameter::

        from nebius.aio.token.static import EnvBearer
        from nebius.aio.authorization.token import TokenProvider
        from nebius.sdk import SDK

        bearer = EnvBearer("NEBIUS_IAM_TOKEN")
        provider = TokenProvider(bearer)
        sdk = SDK(credentials=provider)  # illustrative only

    """

    def __init__(self, token_provider: token.Bearer) -> None:
        """Create a token provider."""
        super().__init__()
        self._provider = token_provider

    def authenticator(self) -> Authenticator:
        """Return a fresh :class:`TokenAuthenticator` for a request.

        :returns: A token-based authenticator instance.
        :rtype: :class:`TokenAuthenticator`
        """
        return TokenAuthenticator(self._provider.receiver())
