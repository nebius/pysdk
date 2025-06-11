import asyncio
import ssl
import sys
import urllib.parse
import webbrowser
from logging import getLogger
from typing import TextIO

import aiohttp
from attr import dataclass

from nebius.base.tls_certificates import get_system_certificates

from .constants import AUTH_ENDPOINT, TOKEN_ENDPOINT
from .is_wsl import is_wsl
from .pkce import PKCE
from .server import CallbackHandler

log = getLogger(__name__)


@dataclass
class GetTokenResult:
    access_token: str
    expires_in: int | None = None


def https_url(raw_url: str) -> str:
    if not raw_url.startswith(("http://", "https://")):
        return f"https://{raw_url}"
    return raw_url


async def open_browser(url: str) -> None:
    if sys.platform.startswith("linux") and is_wsl():
        import subprocess

        subprocess.run(  # noqa: S603
            ["cmd.exe", "/c", "start", url.replace("&", "^&")],  # noqa: S607
            check=True,
        )
    else:
        webbrowser.open(url)
    return None


async def get_code(
    client_id: str,
    auth_endpoint: str,
    federation_id: str,
    pkce_code: PKCE,
    writer: TextIO | None = None,
    no_browser_open: bool = False,
    timeout: float | None = 300,
) -> tuple[str, str]:
    auth_url = urllib.parse.urlparse(auth_endpoint)
    callback = CallbackHandler()
    await callback.listen_and_serve()

    redirect_uri = callback.addr

    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": "openid",
        "state": callback.state,
        "redirect_uri": redirect_uri,
        "code_challenge": pkce_code.challenge,
        "code_challenge_method": pkce_code.method,
    }
    if federation_id:
        params["federation-id"] = federation_id

    query = urllib.parse.urlencode(params)
    full_auth_url = auth_url._replace(query=query).geturl()

    if no_browser_open:
        msg = (
            "To complete the authentication process, open this link in your"
            f" browser:\n{full_auth_url}"
        )
        log.debug(
            "Browser won't be opened. Show link to user.", extra={"url": full_auth_url}
        )
        if writer:
            print(msg, file=writer)
        else:
            log.info(msg)
    else:
        msg = (
            "Switch to your browser to complete login. If it didn't open "
            f"automatically, use:\n{full_auth_url}"
        )
        log.debug("Attempting to open browser.", extra={"url": full_auth_url})
        if writer:
            print(msg, file=writer)
        else:
            log.info(msg)
        try:
            await open_browser(full_auth_url)
        except Exception as browser_err:
            await callback.shutdown()
            raise RuntimeError(f"Failed to open browser: {browser_err}")

    try:
        code = await asyncio.wait_for(callback.wait_for_code(), timeout=timeout)
        if not code:
            raise RuntimeError("No code received from the callback")
        return code, redirect_uri
    except asyncio.TimeoutError:
        raise TimeoutError("Timeout waiting for auth code")
    finally:
        await callback.shutdown()


async def get_token(
    client_id: str,
    token_url: str,
    code: str,
    redirect_uri: str,
    verifier: str,
    ssl_ctx: ssl.SSLContext | None = None,
) -> GetTokenResult:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    }
    if ssl_ctx is None:
        root_ca = get_system_certificates()
        ssl_ctx = ssl.create_default_context(cafile=root_ca)

    async with aiohttp.ClientSession() as session:
        async with session.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            ssl=ssl_ctx,
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"Token request failed: {resp.status} {body}")
            ret = await resp.json()
            if not isinstance(ret, dict):
                raise RuntimeError(f"Unexpected response format: {ret}, expected dict")
            tok = ret.get("access_token", "")  # type: ignore[unused-ignore]
            expires_in = ret.get("expires_in", None)  # type: ignore[unused-ignore]
            if not isinstance(tok, str):
                raise RuntimeError(
                    f"Invalid token response: {ret}, expected 'access_token' as str"
                )
            if expires_in is not None and not isinstance(expires_in, int):
                raise RuntimeError(
                    f"Invalid token response: {ret}, expected 'expires_in' as int or"
                    " None"
                )
            return GetTokenResult(access_token=tok, expires_in=expires_in)


async def authorize(
    client_id: str,
    federation_endpoint: str,
    federation_id: str,
    writer: TextIO | None = None,
    no_browser_open: bool = False,
    timeout: float | None = 300,
    ssl_ctx: ssl.SSLContext | None = None,
) -> GetTokenResult:
    token_url = urllib.parse.urljoin(https_url(federation_endpoint), TOKEN_ENDPOINT)
    auth_url = urllib.parse.urljoin(https_url(federation_endpoint), AUTH_ENDPOINT)

    pkce = PKCE()

    code, redirect_uri = await get_code(
        client_id=client_id,
        auth_endpoint=auth_url,
        federation_id=federation_id,
        pkce_code=pkce,
        writer=writer,
        no_browser_open=no_browser_open,
        timeout=timeout,
    )

    log.debug("Auth code received")

    token = await get_token(
        client_id=client_id,
        token_url=token_url,
        code=code,
        redirect_uri=redirect_uri,
        verifier=pkce.verifier,
        ssl_ctx=ssl_ctx,
    )

    log.debug("Access token received")
    return token
