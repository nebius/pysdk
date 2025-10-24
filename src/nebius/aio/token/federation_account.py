"""High-level federation bearer that provides cached, renewable tokens.

This module exposes :class:`FederationBearer`, a convenience bearer that
composes the interactive federation authorization implementation
(:class:`nebius.aio.token.federation_bearer.Bearer`) with the
asynchronous file-backed renewable cache
(:class:`nebius.aio.token.file_cache.async_renewable_bearer.AsynchronousRenewableFileCacheBearer`).

Behavior and authorization flow
-------------------------------

When a token is requested via :meth:`nebius.aio.token.token.Receiver.fetch` the
following sequence may occur:

1. The cache is consulted for a fresh token. If a cached token is valid it
   is returned immediately.
2. If renewal is required the underlying interactive flow is invoked. This
   flow is implemented by :class:`nebius.aio.token.federation_bearer.Receiver`
   and will typically:

     - construct an authorization URL and attempt to open the user's
       browser (unless ``no_browser_open`` is set), or return the URL so callers
       can display it.
     - block while waiting for the user to complete the authorization in the
       browser (for example by granting access). This means the fetch may hang
       until the user completes the flow.
     - receive an access token and expiration and return it to the caller.

Where the URL is shown
~~~~~~~~~~~~~~~~~~~~~~

- The interactive helper logs the authorization URL so it appears in the
  application's logs.
- If a ``writer`` stream is provided the helper will also write the URL and
  short instructions to that stream (e.g. ``stdout``), which is useful for
  headless environments.

Usage
-----

The :class:`FederationBearer` wraps the interactive bearer with a
file-backed renewable cache and exposes the usual :meth:`receiver` API::

    fb = FederationBearer(profile_name, client_id, endpoint, federation_id)
    token = await fb.receiver().fetch()

Note that because interactive authorization may block, callers should use
timeouts or call fetch from a background task when appropriate.
"""

from datetime import timedelta
from ssl import SSLContext
from typing import TextIO

from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import Receiver

from .federation_bearer import Bearer as FederationAuthBearer
from .file_cache.async_renewable_bearer import AsynchronousRenewableFileCacheBearer


class FederationBearer(ParentBearer):
    """Bearer composing interactive federation auth with a renewable cache.

    The bearer constructs an internal
    :class:`nebius.aio.token.federation_bearer.Bearer` configured with the
    provided parameters and wraps it in an
    :class:`AsynchronousRenewableFileCacheBearer` to provide persistent
    caching and background refresh.


    Behavior and authorization flow
    -------------------------------

    When a token is requested via :meth:`nebius.aio.token.token.Receiver.fetch` the
    following sequence may occur:

    1. The cache is consulted for a fresh token. If a cached token is valid it
        is returned immediately.
    2. If renewal is required the underlying interactive flow is invoked. This
        flow is implemented by :class:`nebius.aio.token.federation_bearer.Receiver`
        and will typically:

            - construct an authorization URL and attempt to open the user's
                browser (unless ``no_browser_open`` is set), or return the URL so
                callers can display it.
            - block while waiting for the user to complete the authorization in the
                browser (for example by granting access). This means the fetch may hang
                until the user completes the flow.
            - receive an access token and expiration and return it to the caller.

    Where the URL is shown
    ~~~~~~~~~~~~~~~~~~~~~~

    - The interactive helper logs the authorization URL so it appears in the
        application's logs.
    - If a ``writer`` stream is provided the helper will also write the URL and
        short instructions to that stream (e.g. ``stdout``), which is useful for
        headless environments.

    :param profile_name: Human-readable profile name included in the bearer's
        :attr:`nebius.aio.token.token.Bearer.name` and used as part of the cache key.
    :param client_id: OAuth2 client identifier used by the interactive flow.
    :param federation_endpoint: Federation endpoint URL.
    :param federation_id: Identifier of the federation configuration.
    :param writer: Optional text stream to which the interactive helper will
        write the authorization URL and short instructions.
    :param no_browser_open: When true the helper will not attempt to open a
        browser automatically and will instead rely on the provided ``writer``
        or logs to surface the URL to the user.
    :param timeout: Timeout forwarded to synchronous refresh requests.
    :param max_retries: Default maximum retry attempts for the receiver.
    :param initial_safety_margin: Safety margin used when deciding whether a
        cached token is considered too close to expiry. May be a timedelta or
        seconds value.
    :param retry_safety_margin: Safety margin subtracted when computing the
        initial retry interval for the background loop.
    :param lifetime_safe_fraction: Fraction of the token lifetime used to
        schedule proactive refreshes.
    :param initial_retry_timeout: Initial backoff timeout used after failures.
    :param max_retry_timeout: Maximum backoff timeout.
    :param retry_timeout_exponent: Exponent used for exponential backoff.
    :param file_cache_throttle: Throttle interval passed to the file cache
        layer to reduce disk reads.
    :param ssl_ctx: Optional SSL context used for HTTPS requests.

    Example
    -------

    Construct a bearer and use it to initialize the SDK::

        from nebius.sdk import SDK
        from nebius.aio.token.federation_account import FederationBearer
        import sys

        sdk = SDK(credentials=FederationBearer(
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
        timeout: timedelta = timedelta(minutes=5),
        max_retries: int = 2,
        initial_safety_margin: timedelta | float | None = timedelta(hours=2),
        retry_safety_margin: timedelta = timedelta(hours=2),
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        file_cache_throttle: timedelta | float = timedelta(minutes=5),
        ssl_ctx: SSLContext | None = None,
    ) -> None:
        """Initialize the federation bearer with renewable file cache."""
        self._source = AsynchronousRenewableFileCacheBearer(
            FederationAuthBearer(
                profile_name=profile_name,
                client_id=client_id,
                federation_endpoint=federation_endpoint,
                federation_id=federation_id,
                writer=writer,
                no_browser_open=no_browser_open,
                ssl_ctx=ssl_ctx,
            ),
            max_retries=max_retries,
            initial_safety_margin=initial_safety_margin,
            retry_safety_margin=retry_safety_margin,
            lifetime_safe_fraction=lifetime_safe_fraction,
            initial_retry_timeout=initial_retry_timeout,
            max_retry_timeout=max_retry_timeout,
            retry_timeout_exponent=retry_timeout_exponent,
            refresh_request_timeout=timeout,
            file_cache_throttle=file_cache_throttle,
        )

    @property
    def wrapped(self) -> "ParentBearer|None":
        """Return the wrapped bearer instance."""
        return self._source

    def receiver(self) -> "Receiver":
        """Return a receiver from the underlying renewable file cache bearer."""
        return self._source.receiver()
