"""Static token bearer and receiver implementations.

This module contains simple bearer and receiver implementations useful for
local testing or when a fixed access token is made available (for example via
an environment variable). The ``EnvBearer`` reads the token from an
environment variable (by default :data:`nebius.base.constants.TOKEN_ENV`) and
``Bearer`` accepts a pre-configured :class:`Token` instance or raw token
string.

Examples
--------
Create a bearer from an explicit token string::

    from nebius.aio.token.static import Bearer

    bearer = Bearer("my-static-token")
    receiver = bearer.receiver()
    token = await receiver.fetch()

Use an environment variable::

    import os
    os.environ["NEBIUS_IAM_TOKEN"] = "token-from-env"
    from nebius.aio.token.static import EnvBearer

    bearer = EnvBearer()  # reads NEBIUS_IAM_TOKEN by default
    receiver = bearer.receiver()
    token = await receiver.fetch()
"""

import os
from logging import getLogger

from nebius.base.constants import TOKEN_ENV
from nebius.base.error import SDKError

from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

log = getLogger(__name__)


class NoTokenInEnvError(SDKError):
    """Raised when an expected environment variable does not contain a token."""

    def __init__(self, env: str) -> None:
        """Initialize the error.

        :param env: Environment variable name that was expected to contain a
            token but was empty or missing.
        """
        super().__init__(f"No token found in the environment variable: {env}")


class Receiver(ParentReceiver):
    """A receiver that returns a pre-configured static token.

    This receiver is useful when the token is known in advance (for
    example embedded in configuration or provided via an environment
    variable). The receiver simply returns the supplied :class:`Token` and
    never indicates that a retry would be useful.

    :param token: Token instance to be returned by :meth:`_fetch`.
    """

    def __init__(self, token: Token) -> None:
        """Create a static receiver using the token."""
        super().__init__()
        self._latest = token

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Return the configured token.

        The receiver returns the pre-configured token. If no token is configured
        `SDKError` is raised since the class invariant is that a static receiver must
        be constructed with a token instance.

        :param timeout: Ignored for static receiver but accepted for API
            compatibility.
        :param options: Ignored. Present for API compatibility.
        :returns: The configured :class:`Token`.
        :raises SDKError: If the internal token is `None` (should not happen when used
            correctly).
        """
        if self._latest is None:
            raise SDKError("Token has to be set")
        log.debug("static token fetched")
        return self._latest

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Static tokens are immutable and cannot be refreshed; never retry.

        :param err: The exception that caused a previous authentication
            failure (ignored).
        :param options: Ignored; present for API compatibility.
        :returns: Always `False`.
        """
        return False


class Bearer(ParentBearer):
    """Bearer that supplies a static token to authenticators.

    The bearer may be constructed with either a :class:`Token` instance or a
    raw token string. When a string is provided it is converted into a
    :class:`Token`. Empty token strings are rejected.

    :param token: :class:`Token` instance or raw token string.
    :type token: :class:`Token` or `str`
    :raises SDKError: When an empty token string is provided.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from nebius.sdk import SDK
        from nebius.aio.token.static import Bearer

        sdk = SDK(credentials=Bearer("my-static-token"))
    """

    def __init__(self, token: Token | str) -> None:
        """Initialize the static token bearer."""
        if isinstance(token, str):
            token = Token(token)
        if token.token == "":
            raise SDKError("empty token provided")
        super().__init__()
        self._tok = token

    def receiver(self) -> Receiver:
        """Return a :class:`Receiver` that yields the configured token.

        :returns: A :class:`Receiver` bound to the static token.
        """
        return Receiver(self._tok)


class EnvBearer(Bearer):
    """Bearer that reads the token from an environment variable.

    :param env_var_name: Environment variable name to read the token from.
        Defaults to :data:`nebius.base.constants.TOKEN_ENV`.
    :type env_var_name: `str`
    :raises NoTokenInEnvError: When the environment variable is not set or
        empty.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        import os
        from nebius.sdk import SDK
        from nebius.aio.token.static import EnvBearer

        os.environ["NEBIUS_IAM_TOKEN"] = "token-from-env"
        sdk = SDK(credentials=EnvBearer())
    """

    def __init__(self, env_var_name: str = TOKEN_ENV) -> None:
        """Initialize the environment-variable based bearer."""
        val = os.environ.get(env_var_name, "")
        if val == "":
            raise NoTokenInEnvError(env_var_name)
        super().__init__(val)
