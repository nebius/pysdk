"""Asynchronous bearer token abstractions and the token representation.

This module provides the core abstractions used by the SDK for representing
bearer tokens and for supplying per-request token receivers.

Key classes
-----------

- :class:`Token` -- simple immutable representation of an access token and an
    optional expiration time.
- :class:`Receiver` -- asynchronous primitive that can fetch a single
    :class:`Token` (used per-request by the authentication layer).
- :class:`Bearer` -- provider of :class:`Receiver` instances. Bearers are
    composed to add features like naming, renewal and caching.

Examples
--------
Create a simple token and serialize it::

        from nebius.aio.token.token import Token
        from datetime import datetime, timezone, timedelta

        tok = Token(
                "s3cr3t",
                expiration=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        print(str(tok))
        data = tok.to_dict()

Restore the token from the serialized form::

        tok2 = Token.from_dict(data)
        assert tok == tok2

Using a static bearer/receiver (see :mod:`nebius.aio.token.static` for
concrete implementations) the SDK creates per-request receivers with
``bearer.receiver()`` and uses :meth:`Receiver.fetch` to obtain tokens.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from nebius.base.token_sanitizer import TokenSanitizer

sanitizer = TokenSanitizer.access_token_sanitizer()


class Token:
    """Representation of a bearer token with optional expiration.

    Behaviour notes
    ---------------
    - ``str(Token)`` returns a sanitized representation using
      :class:`nebius.base.token_sanitizer.TokenSanitizer` to avoid logging
      secrets in plaintext. When expiration is present, the ISO timestamp and
      a relative ``expires_in`` delta are included in the representation.
    - ``to_dict`` serializes the token into a mapping with ``token`` and
      ``expires_at`` keys, where ``expires_at`` is an integer POSIX timestamp
      (or ``None`` when no expiration was set).

    :param token: The raw token string. May be empty for an "empty" token.
    :type token: `str`
    :param expiration: Optional UTC-aware expiration datetime. If provided,
        :meth:`is_expired` checks against this value.
    :type expiration: :class:`datetime.datetime` or `None`
    """

    def __init__(self, token: str, expiration: datetime | None = None) -> None:
        """Initialize a token with these token string and expiration"""
        self._tok = token
        self._exp = expiration

    def __str__(self) -> str:
        """Return a short, sanitized string representation.

        :returns: A one-line safe representation of the token for debugging.
        :rtype: `str`
        """
        if self.is_empty():
            return "Token(empty)"
        ret = ["Token("]
        ret.append(sanitizer.sanitize(self._tok))
        if self._exp is not None:
            ret.append(f", expiration={self._exp.isoformat()}")
            expires_in = self._exp - datetime.now(timezone.utc)
            ret.append(f", expires_in={expires_in}")
        else:
            ret.append(", expiration=None")
        ret.append(")")
        return "".join(ret)

    @classmethod
    def empty(cls) -> "Token":
        """Create an empty token.

        :returns: A :class:`Token` instance representing the absence of a
            credential (empty token string).
        :rtype: :class:`Token`
        """
        return cls(token="")

    @property
    def token(self) -> str:
        """The raw token string.

        :rtype: `str`
        """
        return self._tok

    @property
    def expiration(self) -> datetime | None:
        """The UTC-aware expiration datetime, or ``None`` if not set.

        :rtype: :class:`datetime.datetime` or `None`
        """
        return self._exp

    def is_empty(self) -> bool:
        """Return `True` when the token string is empty.

        :returns: `True` when this token represents no credential.
        """
        return self._tok == ""

    def is_expired(self) -> bool:
        """Return `True` when the token is expired.

        When ``expiration`` is `None`, tokens are considered non-expiring and
        this method returns `False`.

        :returns: `True` if the current UTC time is equal to or after the
            expiration instant.
        :rtype: bool
        """
        if self._exp is None:
            return False
        return datetime.now(timezone.utc) >= self._exp

    def to_dict(self) -> dict[str, Any]:
        """Serialize the token to a mapping.

        The mapping contains ``token`` and ``expires_at``. ``expires_at`` is
        an integer POSIX timestamp when an expiration is set, otherwise
        ``None``.

        :returns: A dictionary serializable to JSON.
        :rtype: `dict`
        """
        expires_at = int(self._exp.timestamp()) if self._exp is not None else 0
        data: dict[str, Any] = {
            "token": self._tok,
            "expires_at": expires_at if self._exp is not None else None,
        }
        return data

    def __eq__(self, value: object) -> bool:
        """Equality comparison.

        Two tokens are equal when both their token strings and expiration
        datetimes are equal.

        :param value: Other object to compare.
        :returns: `True` when equal, otherwise `False`.
        """
        if not isinstance(value, Token):
            return NotImplemented
        return self._tok == value._tok and self._exp == value._exp

    @classmethod
    def from_dict(cls, data: Any) -> "Token":
        """Create a Token from a mapping produced by :meth:`to_dict`.

        :param data: Mapping with at least the ``token`` key and optional
            ``expires_at`` integer timestamp.
        :type data: :class:`typing.Any`
        :raises ValueError: When the input type is invalid or contains
            incompatible types.
        :returns: A :class:`Token` instance parsed from the mapping.
        :rtype: :class:`Token`
        """
        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid format for Token: {type(data)} expected a dictionary.",
            )
        token = data.get("token", "")  # type: ignore[assignment,unused-ignore]
        if token is None:
            token = ""
        if not isinstance(token, str):
            raise ValueError(f"Invalid token format: {type(token)} expected a string.")  # type: ignore[assignment,unused-ignore]
        expires_at = data.get("expires_at", None)  # type: ignore[assignment,unused-ignore]
        if expires_at is None:
            return cls(token=token)
        if not isinstance(expires_at, int):
            raise ValueError(
                f"Invalid expires_at format: {type(expires_at)} expected an int."  # type: ignore[assignment,unused-ignore]
            )
        expiration = (
            datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None
        )
        return cls(token=token, expiration=expiration)


class Receiver(ABC):
    """Abstract asynchronous token receiver interface.

    Implementations fetch bearer tokens from an external source (for
    example an OAuth token endpoint or a local cache) and expose a small API
    that the request layer uses to obtain tokens for per-request
    authentication.

    The receiver is responsible for fetching and refreshing the token for one request
    only, reflecting the authentication process, while the :class:`Bearer` class
    supports multiple requests and provides per-request receivers on demand.
    """

    _latest: Token | None
    """The most recently fetched token, or `None` if no token has been
    fetched yet. Implementations may update this to support inspection or
    caching by callers.
    """

    @abstractmethod
    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Low-level asynchronous fetch implementation.

        Subclasses must implement this method to perform the actual token
        retrieval. This method is intentionally prefixed with an underscore to
        indicate it is the minimal primitive; callers should use
        :meth:`fetch` which records the result in ``_latest``.

        :param timeout: Optional timeout in seconds for the fetch operation.
        :type timeout: optional `float`
        :param options: Optional implementation-specific options forwarded by
            the request layer.
        :type options: optional ``dict[str, str]``
        :returns: A freshly fetched :class:`Token`.
        :rtype: :class:`Token`
        """
        raise NotImplementedError("Method not implemented!")

    @property
    def latest(self) -> Token | None:
        """Return the latest fetched token or ``None``.

        :rtype: :class:`Token` or None
        """
        return self._latest

    async def fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Fetch a token and record it as the latest value.

        This method calls the concrete :meth:`_fetch` implementation and stores
        the result on :attr:`_latest` before returning it.

        :param timeout: Optional timeout in seconds forwarded to the fetch.
        :type timeout: optional `float`
        :param options: Optional implementation-specific options.
        :type options: optional ``dict[str, str]``
        :returns: The fetched :class:`Token`.
        :rtype: :class:`Token`
        """
        tok = await self._fetch(timeout=timeout, options=options)
        self._latest = tok
        return tok

    @abstractmethod
    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Decide whether a failed authentication attempt should be retried.

        Implementations inspect ``err`` (for example gRPC status codes or
        specific exception types) and optional ``options`` to decide whether a
        fresh call to :meth:`fetch` is likely to succeed (for example after
        refreshing credentials).

        Default implementations should return `False`.

        :param err: The exception that triggered the retry decision.
        :type err: `Exception`
        :param options: Optional implementation-specific options.
        :type options: ``dict[str, str]`` or `None`
        :returns: `True` when a retry is advisable, otherwise `False`.
        """
        return False


class Bearer(ABC):
    """Abstract provider of :class:`Receiver` instances.

    A Bearer supplies receivers for per-request authenticators. Bearers may
    be composed (wrapping other Bearers) to add behaviour such as caching,
    refreshing, or naming.

    Example
    -------

    Implement a custom bearer::

        from nebius.sdk import SDK
        from nebius.aio.token.token import Bearer, Receiver, Token

        class MyBearer(Bearer):
            def receiver(self) -> Receiver:
                return MyReceiver()

        class MyReceiver(Receiver):
            async def _fetch(self, timeout=None, options=None) -> Token:
                return Token("my-token")

            def can_retry(self, err, options=None) -> bool:
                return False

        sdk = SDK(credentials=MyBearer())
    """

    @abstractmethod
    def receiver(self) -> Receiver:
        """Return a :class:`Receiver` to be used for a single request.

        Implementations should return a receiver that can safely be used by
        a single request/Authenticator instance. It may return a shared
        receiver or create a new one depending on the provider semantics.

        :returns: A fresh and unique token :class:`Receiver`.
        :rtype: :class:`Receiver`
        """
        raise NotImplementedError("Method not implemented!")

    @property
    def name(self) -> str | None:
        """Optional human-readable name for the bearer.

        This may be used in some wrapper providers to cache the results of
        the shared receiver, or to report diagnostics.

        This name should reflect the unique configuration of the bearer.

        If the bearer wraps another bearer, the default behaviour is to
        forward the name lookup to the wrapped instance.

        :rtype: `str` or `None`
        """
        if self.wrapped is not None:
            return self.wrapped.name
        return None

    @property
    def wrapped(self) -> "Bearer|None":
        """Return the wrapped bearer or `None` if not wrapping.

        Subclasses that decorate or compose another bearer should override this
        property to return the inner bearer.

        :rtype: :class:`Bearer` or `None`
        """
        return None

    async def close(self, grace: float | None = None) -> None:
        """Close the bearer and any wrapped resources.

        :param grace: Optional graceful shutdown timeout in seconds.
        :type grace: optional `float`
        """
        if self.wrapped is not None:
            await self.wrapped.close(grace=grace)
        return None


class NamedBearer(Bearer):
    """Simple bearer wrapper that attaches a static name to another bearer.

    This may be used in some wrapper providers to cache the results of
    the shared receiver, or to report diagnostics.

    This name should reflect the unique configuration of the underlying bearer.

    :param wrapped: The inner bearer to delegate to.
    :type wrapped: :class:`Bearer`
    :param name: The :meth:`name` that reflects the configuration of the underlying
        bearer.

    Example
    -------

    Wrap a custom bearer with a name and file cache::

        from nebius.sdk import SDK
        from nebius.aio.token.token import NamedBearer, Bearer, Receiver, Token
        from nebius.aio.token.file_cache.async_renewable_bearer import (
            AsynchronousRenewableFileCacheBearer
        )

        class SomeCustomHeavyLoadBearer(Bearer):
            def receiver(self) -> Receiver:
                return SomeReceiver()

        class SomeReceiver(Receiver):
            async def _fetch(self, timeout=None, options=None) -> Token:
                # Simulate heavy load token fetch
                return Token("heavy-token")

            def can_retry(self, err, options=None) -> bool:
                return False

        custom_bearer = SomeCustomHeavyLoadBearer()
        named_bearer = NamedBearer(custom_bearer, "heavy-load-bearer")
        cached_bearer = AsynchronousRenewableFileCacheBearer(named_bearer)

        sdk = SDK(credentials=cached_bearer)
    """

    def __init__(self, wrapped: Bearer, name: str) -> None:
        """Wrap the passed-in bearer, attaching a name to it.

        This name should reflect the unique configuration of the underlying bearer.
        """
        self._wrapped = wrapped
        self._name = name

    @property
    def wrapped(self) -> Bearer:
        """Return the wrapped bearer."""
        return self._wrapped

    @property
    def name(self) -> str | None:
        """Return the configured name for this bearer.

        :returns: Always returns a name.
        :rtype: `str`
        """
        return self._name

    def receiver(self) -> Receiver:
        """Delegate to the wrapped bearer to obtain a receiver.

        :returns: A :class:`Receiver` obtained from the wrapped bearer.
        """
        return self._wrapped.receiver()
