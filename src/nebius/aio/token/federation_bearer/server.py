"""Federation bearer token server for handling OAuth callbacks.

This module provides a CallbackHandler class that sets up a local HTTP server
to handle OAuth authorization code callbacks during federation bearer token
authentication flows. It uses PKCE (Proof Key for Code Exchange) for security.
"""

import asyncio
import socket
from logging import getLogger

from aiohttp import web

from .pkce import PKCE

log = getLogger(__name__)


class CallbackHandler:
    """Handler for OAuth callback server during federation authentication.

    This class manages a local HTTP server that listens for OAuth authorization
    code callbacks. It validates the state using PKCE and extracts the authorization
    code for token exchange.
    """

    def __init__(self) -> None:
        self._code: str | None = None
        self._state: str = PKCE().verifier
        self._done = asyncio.Event()
        self._lock = asyncio.Lock()
        self._app = web.Application()
        self._runner: web.AppRunner | None = None
        self._site: web.SockSite | None = None
        self._port: int | None = None
        self._addr: str | None = None

        self._app.router.add_get("/", self._handle_callback)

    @property
    def state(self) -> str:
        """The PKCE state verifier used for callback validation.

        :return: The state string.
        :rtype: str
        """
        return self._state

    @property
    def code(self) -> str | None:
        """The authorization code received from the OAuth callback.

        :return: The authorization code or None if not received.
        :rtype: str or None
        """
        return self._code

    @property
    def port(self) -> int | None:
        """The port number the server is listening on.

        :return: The port number or None if not started.
        :rtype: int or None
        """
        return self._port

    @property
    def addr(self) -> str:
        """The full address of the callback server.

        :return: The address in the format http://addr:port.
        :rtype: str
        """
        return f"http://{self._addr}:{self._port}"

    async def _handle_callback(self, request: web.Request) -> web.Response:
        """Handle the OAuth callback request.

        Extracts the authorization code and state from the query parameters,
        validates the state, and sets the code if valid.

        :param request: The incoming HTTP request.
        :return: The HTTP response to send back.
        """
        code = request.query.get("code")
        state = request.query.get("state")
        await self._set_code(code, state)

        if self._code and state == self._state:
            return web.Response(
                text="Login is successful, you may close the browser tab and go to the "
                "console"
            )
        return web.Response(
            status=400,
            text="Login is not successful, you may close the browser tab and try again",
        )

    async def _set_code(self, code: str | None, state: str | None) -> None:
        """Set the authorization code if the state is valid.

        :param code: The authorization code from the callback.
        :type code: str or None
        :param state: The state parameter from the callback.
        :type state: str or None
        """
        async with self._lock:
            if self._done.is_set():
                return
            if code and state == self._state:
                self._code = code
            self._done.set()

    async def listen_and_serve(self) -> None:
        """Start the HTTP server on a free port.

        Binds to localhost on a free port and starts listening for callbacks.
        """
        port, sock, addr = self._get_free_port()
        self._port = port
        self._addr = addr
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.SockSite(self._runner, sock)
        await self._site.start()
        log.info(f"Server started on {self.addr}")

    def _get_free_port(self) -> tuple[int, socket.socket, str]:
        """Find and bind to a free port on localhost.

        :return: A tuple of (port, socket, address).
        :rtype: tuple[int, socket.socket, str]
        """
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                sock = socket.socket(family, socket.SOCK_STREAM)
                sock.bind(("localhost", 0))
                port = sock.getsockname()[1]
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                return port, sock, "127.0.0.1" if family == socket.AF_INET else "[::1]"
            except OSError:
                continue
        raise RuntimeError("No available ports")

    async def shutdown(self) -> None:
        """Shutdown the HTTP server.

        Stops the site and cleans up the runner.
        """
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

    async def wait_for_code(self, timeout: float | None = None) -> str | None:
        """Wait for the authorization code to be received.

        :param timeout: Optional timeout in seconds.
        :type timeout: float or None
        :return: The authorization code or None if timed out.
        :rtype: str or None
        """
        await asyncio.wait_for(self._done.wait(), timeout=timeout)
        return self._code
