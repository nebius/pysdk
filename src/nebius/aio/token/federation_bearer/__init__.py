"""Federated bearer allowing interactive authorization flows.

This module provides a small bearer implementation that performs an
interactive federation-based authorization to obtain short-lived access
tokens. It is intended for scenarios where a user needs to authorize a
local client by opening a browser or presenting a URL to the user.

Interactive authorization flow (what happens on ``fetch``)
----------------------------------------------------------

When :meth:`Receiver._fetch` is invoked the implementation will call the
helper :func:`nebius.aio.token.federation_bearer.auth.authorize` which
performs the interactive federation handshake. The typical flow is:

1. The helper constructs an authorization URL and either attempts to open
     the user's default browser or returns the URL for the caller to display.
2. The helper will block while waiting for the user to complete the
     authorization in the browser (for example by granting access). This means
     ``Receiver._fetch`` may hang until the user completes the flow.
3. The helper receives an authorization response containing an access token
     and expiry. The receiver converts this into a
     :class:`nebius.aio.token.token.Token` and returns it to the caller.

Where the URL is shown
----------------------

- The authorization URL is logged at INFO/DEBUG levels so it appears in the project's
    logs.
- If a ``writer`` text stream is provided to the :class:`Receiver` or
    the :class:`Bearer`, the URL (and short instructions) will also be written
    to that stream so callers can present it directly to a user (for example
    printing to stdout).

Blocking considerations
-----------------------

Because the flow waits for the user's action, callers should be aware that
``fetch`` can block for an extended period. Use reasonable timeouts when
calling :meth:`Receiver._fetch` or invoke the bearer within a background
task if you need the application to remain responsive.

Classes
-------

- :class:`Receiver` -- A receiver that executes the interactive
    authorization flow and returns a :class:`nebius.aio.token.token.Token`.
- :class:`Bearer` -- A small bearer wrapper exposing the receiver and a
    canonical :attr:`Bearer.name` used for caching and logging.

Example
-------

Construct a bearer and fetch a token::

        bearer = Bearer(profile_name, client_id, endpoint, federation_id)
        token = await bearer.receiver().fetch()

"""

from asyncio import Task
from datetime import datetime, timedelta, timezone
from logging import getLogger
from ssl import SSLContext
from typing import Any, TextIO, TypeVar

from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import Receiver as ParentReceiver
from nebius.aio.token.token import Token

log = getLogger(__name__)


class Receiver(ParentReceiver):
    """Receiver that runs the federation interactive authorization.

    Interactive authorization flow (what happens on ``fetch``)
    ----------------------------------------------------------

    When :meth:`Receiver._fetch` is invoked the implementation will call the
    helper :func:`nebius.aio.token.federation_bearer.auth.authorize` which
    performs the interactive federation handshake. The typical flow is:

    1. The helper constructs an authorization URL and either attempts to open
        the user's default browser or returns the URL for the caller to display.
    2. The helper will block while waiting for the user to complete the
        authorization in the browser (for example by granting access). This means
        ``Receiver._fetch`` may hang until the user completes the flow.
    3. The helper receives an authorization response containing an access token
        and expiry. The receiver converts this into a
        :class:`nebius.aio.token.token.Token` and returns it to the caller.

    Where the URL is shown
    ----------------------

    - The authorization URL is logged at INFO/DEBUG levels so it appears in the
        project's logs.
    - If a ``writer`` text stream is provided to the :class:`Receiver` or
        the :class:`Bearer`, the URL (and short instructions) will also be written
        to that stream so callers can present it directly to a user (for example
        printing to stdout).

    Blocking considerations
    -----------------------

    Because the flow waits for the user's action, callers should be aware that
    ``fetch`` can block for an extended period. Use reasonable timeouts when
    calling :meth:`Receiver._fetch` or invoke the bearer within a background
    task if you need the application to remain responsive.

    :param client_id: OAuth2 client identifier used during authorization.
    :param federation_endpoint: URL of the federation endpoint.
    :param federation_id: Identifier of the users federation.
    :param writer: Optional text writer used to display instructions to the user.
    :param no_browser_open: If true the implementation will not attempt to
        open a browser automatically but will just print a URL to the ``writer`` and
        logs.
    :param ssl_ctx: Optional SSL context to use for HTTPS requests.
    """

    def __init__(
        self,
        client_id: str,
        federation_endpoint: str,
        federation_id: str,
        writer: TextIO | None = None,
        no_browser_open: bool = False,
        ssl_ctx: SSLContext | None = None,
    ) -> None:
        """Create a federation interactive receiver."""
        self._client_id = client_id
        self._federation_endpoint = federation_endpoint
        self._federation_id = federation_id
        self._writer = writer
        self._no_browser_open = no_browser_open
        self._ssl_ctx = ssl_ctx

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Execute the interactive authorization flow and return a Token.

        The implementation imports and calls
        :func:`nebius.aio.token.federation_bearer.auth.authorize` to
        perform the protocol. The returned access token and expiration
        information are converted into a
        :class:`nebius.aio.token.token.Token`.

        :param timeout: Optional timeout in seconds forwarded to the
            authorization helper.
        :param options: Unused; present for API compatibility.
        :returns: A :class:`Token` containing the access token and expiration.
        """
        from .auth import authorize

        now = datetime.now(timezone.utc)
        tok = await authorize(
            client_id=self._client_id,
            federation_endpoint=self._federation_endpoint,
            federation_id=self._federation_id,
            writer=self._writer,
            no_browser_open=self._no_browser_open,
            timeout=timeout,
            ssl_ctx=self._ssl_ctx,
        )
        return Token(
            token=tok.access_token,
            expiration=(
                now + timedelta(seconds=tok.expires_in)
                if tok.expires_in is not None
                else None
            ),
        )

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Decide whether an authorization error should be retried.

        The current implementation always permits retries. This is a simple
        policy because interactive flows commonly allow a user to retry the
        operation (for example if they decline the prompt initially).

        :param err: The exception raised during fetch.
        :param options: Unused; present for API compatibility.
        :returns: Always `True` in the current implementation.
        """
        return True


T = TypeVar("T")


class Bearer(ParentBearer):
    """Bearer that exposes a federation interactive receiver.

    The bearer is a lightweight wrapper that holds configuration used to
    construct :class:`Receiver` instances. It also exposes a stable
    :attr:`name` used for caching and identification.

    Interactive authorization flow (what happens on ``fetch``)
    ----------------------------------------------------------

    When :meth:`Receiver._fetch` is invoked the implementation will call the
    helper :func:`nebius.aio.token.federation_bearer.auth.authorize` which
    performs the interactive federation handshake. The typical flow is:

    1. The helper constructs an authorization URL and either attempts to open
        the user's default browser or returns the URL for the caller to display.
    2. The helper will block while waiting for the user to complete the
        authorization in the browser (for example by granting access). This means
        ``Receiver._fetch`` may hang until the user completes the flow.
    3. The helper receives an authorization response containing an access token
        and expiry. The receiver converts this into a
        :class:`nebius.aio.token.token.Token` and returns it to the caller.

    Where the URL is shown
    ----------------------

    - The authorization URL is logged at INFO/DEBUG levels so it appears in the
        project's logs.
    - If a ``writer`` text stream is provided to the :class:`Receiver` or
        the :class:`Bearer`, the URL (and short instructions) will also be written
        to that stream so callers can present it directly to a user (for example
        printing to stdout).

    Blocking considerations
    -----------------------

    Because the flow waits for the user's action, callers should be aware that
    ``fetch`` can block for an extended period. Use reasonable timeouts when
    calling :meth:`Receiver._fetch` or invoke the bearer within a background
    task if you need the application to remain responsive.

    :param profile_name: Human-readable profile name that will be included in
        :attr:`name`.
    :param client_id: OAuth2 client identifier.
    :param federation_endpoint: Federation endpoint URL.
    :param federation_id: Identifier of users federation.
    :param writer: Optional text writer used to display instructions.
    :param no_browser_open: When true the receiver will not attempt to open
        a browser automatically.
    :param ssl_ctx: Optional SSL context for HTTPS requests.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from nebius.sdk import SDK
        from nebius.aio.token.federation_bearer import Bearer
        import sys

        sdk = SDK(credentials=Bearer(
            profile_name="not-a-cli-profile",
            client_id="my-client-id",
            federation_endpoint="auth.eu.nebius.com",
            federation_id="federation-e00my-federation",
            writer=sys.stdout,
            no_browser_open=True,
        ))
    """

    def __init__(
        self,
        profile_name: str,
        client_id: str,
        federation_endpoint: str,
        federation_id: str,
        writer: TextIO | None = None,
        no_browser_open: bool = False,
        ssl_ctx: SSLContext | None = None,
    ) -> None:
        """Create a federation interactive bearer."""
        self._profile_name = profile_name
        self._client_id = client_id
        self._federation_endpoint = federation_endpoint
        self._federation_id = federation_id
        self._writer = writer
        self._no_browser_open = no_browser_open
        self._ssl_ctx = ssl_ctx

        self._tasks = set[Task[Any]]()

    @property
    def name(self) -> str:
        return (
            f"federation/{self._federation_endpoint}/{self._federation_id}/"
            f"{self._profile_name}"
        )

    def receiver(self) -> ParentReceiver:
        """Return a new :class:`Receiver` bound to this bearer's configuration.

        :returns: A :class:`Receiver` capable of performing the interactive
            authorization flow.
        """
        return Receiver(
            client_id=self._client_id,
            federation_endpoint=self._federation_endpoint,
            federation_id=self._federation_id,
            writer=self._writer,
            no_browser_open=self._no_browser_open,
            ssl_ctx=self._ssl_ctx,
        )
