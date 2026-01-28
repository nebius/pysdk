"""Federation bearer authentication utilities.

This module provides functions to perform OAuth 2.0 authorization code flow
with PKCE for federation bearer token authentication. It handles browser-based
authentication, callback server management, and token exchange.
"""

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
    """Result of token retrieval.

    :ivar access_token: The access token string.
    :type access_token: str
    :ivar expires_in: Token expiration time in seconds, or None if not provided.
    :type expires_in: int or None
    """

    access_token: str
    expires_in: int | None = None


def https_url(raw_url: str) -> str:
    """Ensure the URL uses HTTPS scheme.

    :param raw_url: The input URL string.
    :type raw_url: str
    :return: The URL with HTTPS scheme.
    :rtype: str
    """
    if not raw_url.startswith(("http://", "https://")):
        return f"https://{raw_url}"
    return raw_url


async def open_browser(url: str) -> None:
    """Open the given URL in the default web browser.

    Handles special case for WSL environments by using cmd.exe.

    :param url: The URL to open.
    :type url: str
    """
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
    """Obtain authorization code via OAuth callback.

    Starts a local callback server, constructs the authorization URL with PKCE,
    opens the browser (or prints the URL), and waits for the callback.

    :param client_id: The OAuth client ID.
    :type client_id: str
    :param auth_endpoint: The authorization endpoint URL.
    :type auth_endpoint: str
    :param federation_id: The federation identifier.
    :type federation_id: str
    :param pkce_code: The PKCE code challenge and method.
    :type pkce_code: :class:`PKCE`
    :param writer: Optional text stream to write messages to.
    :type writer: :class:`TextIO` or None
    :param no_browser_open: If True, do not open browser automatically.
    :type no_browser_open: bool
    :param timeout: Timeout in seconds for waiting for the code.
    :type timeout: float or None
    :return: A tuple of (authorization_code, redirect_uri).
    :rtype: tuple[str, str]
    :raises RuntimeError: If browser fails to open or no code received.
    :raises TimeoutError: If timeout waiting for code.
    """
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
    """Exchange authorization code for access token.

    Sends a POST request to the token endpoint with the code and PKCE verifier.

    :param client_id: The OAuth client ID.
    :type client_id: str
    :param token_url: The token endpoint URL.
    :type token_url: str
    :param code: The authorization code received from callback.
    :type code: str
    :param redirect_uri: The redirect URI used in the request.
    :type redirect_uri: str
    :param verifier: The PKCE code verifier.
    :type verifier: str
    :param ssl_ctx: Optional SSL context for the request.
    :type ssl_ctx: :class:`ssl.SSLContext` or None
    :return: The token result containing access token and expiration.
    :rtype: :class:`GetTokenResult`
    :raises RuntimeError: If token request fails or response is invalid.
    """
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
    """Perform full OAuth authorization flow and return access token.

    Combines getting the authorization code and exchanging it for a token.

    :param client_id: The OAuth client ID.
    :type client_id: str
    :param federation_endpoint: The base federation endpoint URL.
    :type federation_endpoint: str
    :param federation_id: The federation identifier.
    :type federation_id: str
    :param writer: Optional text stream to write messages to.
    :type writer: :class:`TextIO` or None
    :param no_browser_open: If True, do not open browser automatically.
    :type no_browser_open: bool
    :param timeout: Timeout in seconds for the entire flow.
    :type timeout: float or None
    :param ssl_ctx: Optional SSL context for token request.
    :type ssl_ctx: :class:`ssl.SSLContext` or None
    :return: The token result containing access token and expiration.
    :rtype: :class:`GetTokenResult`
    """
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
