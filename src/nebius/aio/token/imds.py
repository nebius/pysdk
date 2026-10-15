"""IMDS token-endpoint credentials."""

from __future__ import annotations

import json
from asyncio import IncompleteReadError, sleep, wait_for
from datetime import datetime, timezone
from typing import Any

import aiohttp

from ...base.error import SDKError
from .token import Bearer as ParentBearer
from .token import Receiver as ParentReceiver
from .token import Token

_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 0.2
_MAX_RESPONSE_BYTES = 64 << 10


class IMDSError(SDKError):
    """Raised when a metadata token endpoint cannot provide a token."""


def _expiration(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise IMDSError("IMDS token response has no valid expires_at value")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise IMDSError("IMDS token response has an invalid expires_at value") from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class Receiver(ParentReceiver):
    """Fetch a token from one IMDS HTTP endpoint for a single SDK request."""

    def __init__(self, endpoint: str) -> None:
        super().__init__()
        self._endpoint = endpoint
        self._fetches = 0
        self._invalid_token: str | None = None
        self._metric_attempt = 0

    async def _fetch(
        self,
        timeout: float | None = None,
        options: dict[str, str] | None = None,
    ) -> Token:
        del options
        self._fetches += 1
        fetch = self._fetch_with_retries()
        if timeout is None:
            return await fetch
        return await wait_for(fetch, timeout)

    async def _fetch_with_retries(self) -> Token:
        async with aiohttp.ClientSession() as session:
            for attempt in range(_MAX_ATTEMPTS):
                self._metric_attempt = attempt + 1
                try:
                    async with session.get(
                        self._endpoint,
                        headers={"Metadata": "true"},
                    ) as response:
                        if response.status == 200:
                            try:
                                body = await response.content.readexactly(_MAX_RESPONSE_BYTES + 1)
                            except IncompleteReadError as error:
                                body = error.partial
                            if len(body) > _MAX_RESPONSE_BYTES:
                                raise IMDSError(f"IMDS response body exceeds {_MAX_RESPONSE_BYTES} bytes")
                            try:
                                payload: Any = json.loads(body)
                            except (TypeError, ValueError):
                                raise IMDSError("could not decode IMDS token response") from None
                            if not isinstance(payload, dict):
                                raise IMDSError("IMDS token response must be a JSON object")
                            access_token = payload.get("access_token")
                            if not isinstance(access_token, str) or not access_token:
                                raise IMDSError("IMDS token response has no access_token")
                            token = Token(
                                access_token,
                                _expiration(payload.get("expires_at")),
                            )
                            if self._invalid_token == token.token:
                                self._invalid_token = None
                                raise IMDSError("IMDS returned the same rejected access token")
                            self._invalid_token = None
                            return token
                        retryable = response.status == 429 or response.status >= 500
                        if not retryable or attempt == _MAX_ATTEMPTS - 1:
                            try:
                                body = await response.content.readexactly(_MAX_RESPONSE_BYTES + 1)
                            except IncompleteReadError as error:
                                body = error.partial
                            except aiohttp.ClientError:
                                raise IMDSError(
                                    f"IMDS token request failed: HTTP {response.status}; could not read response body",
                                ) from None
                            body_text = body[:_MAX_RESPONSE_BYTES].decode("utf-8", errors="replace")
                            if len(body) > _MAX_RESPONSE_BYTES:
                                body_text += "... (truncated)"
                            raise IMDSError(f"IMDS token request failed: HTTP {response.status}: {body_text}")
                except aiohttp.ClientError as error:
                    raise IMDSError(f"request IMDS token: {error}") from error
                await sleep(_BASE_BACKOFF_SECONDS * (attempt + 1))
        raise IMDSError("failed to get IMDS token")

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        del err, options
        if self._fetches >= 2 or self.latest is None:
            return False
        self._invalid_token = self.latest.token
        return True


class Bearer(ParentBearer):
    """Bearer that requests a fresh token from a metadata service."""

    def __init__(self, endpoint: str) -> None:
        if not endpoint:
            raise IMDSError("empty IMDS endpoint")
        self._endpoint = endpoint

    @property
    def name(self) -> str:
        return f"imds:{self._endpoint}"

    @property
    def metrics_provider(self) -> str:
        return "imds"

    def receiver(self) -> Receiver:
        return Receiver(self._endpoint)
