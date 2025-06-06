import asyncio
import socket
from logging import getLogger

from aiohttp import web

from .pkce import PKCE

log = getLogger(__name__)


class CallbackHandler:
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
        return self._state

    @property
    def code(self) -> str | None:
        return self._code

    @property
    def port(self) -> int | None:
        return self._port

    @property
    def addr(self) -> str:
        return f"http://{self._addr}:{self._port}"

    async def _handle_callback(self, request: web.Request) -> web.Response:
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
        async with self._lock:
            if self._done.is_set():
                return
            if code and state == self._state:
                self._code = code
            self._done.set()

    async def listen_and_serve(self) -> None:
        port, sock, addr = self._get_free_port()
        self._port = port
        self._addr = addr
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.SockSite(self._runner, sock)
        await self._site.start()
        log.info(f"Server started on {self.addr}")

    def _get_free_port(self) -> tuple[int, socket.socket, str]:
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
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

    async def wait_for_code(self, timeout: float | None = None) -> str | None:
        await asyncio.wait_for(self._done.wait(), timeout=timeout)
        return self._code
