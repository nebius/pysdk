"""Callback-based SDK metrics helpers.

Metrics are opt-in. Public constructors that accept ``metrics`` or
``auth_metrics`` expect either an object with callback methods or a mapping
whose values are callback functions. Python snake_case names are preferred and
camelCase aliases are accepted for parity with the TypeScript SDK.

Full SDK/config metrics may implement:

- ``config_load(metric: ConfigMetric)``
- ``credentials_resolve(metric: ConfigMetric)``

Auth metrics may implement:

- ``token_acquire(metric: TokenAcquireMetric)``
- ``token_lifetime(metric: TokenLifetimeMetric)``
- ``token_refresh(metric: TokenRefreshMetric)``
- ``cache_hit(metric: CacheMetric)``
- ``cache_miss(metric: CacheMetric)``
- ``cache_store(metric: CacheMetric)``
- ``cache_refresh(metric: CacheMetric)``
- ``cache_invalidate(metric: CacheMetric)``

Callbacks may be synchronous or asynchronous. Async callbacks are scheduled when
emitted from a running event loop and run to completion when emitted from
synchronous code. Callback exceptions are swallowed so metrics collection never
changes request or authentication behavior.
"""

from __future__ import annotations

from asyncio import (
    CancelledError,
    create_task,
    get_running_loop,
)
from asyncio import (
    run as asyncio_run,
)
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from inspect import isawaitable
from time import monotonic
from typing import Literal, cast

from nebius.aio.token.token import Bearer as _TokenBearer
from nebius.aio.token.token import Receiver as _TokenReceiver
from nebius.aio.token.token import Token as _Token

MetricResult = Literal["success", "error"]

METRIC_RESULT_SUCCESS: MetricResult = "success"
METRIC_RESULT_ERROR: MetricResult = "error"
MetricsLike = object | None
"""Object or mapping with optional config and auth metric callbacks."""

AuthMetricsLike = object | None
"""Object or mapping with optional auth metric callbacks."""


@dataclass(frozen=True)
class TokenAcquireMetric:
    """Token acquisition metric payload."""

    provider: str
    result: MetricResult
    duration_seconds: float
    attempt: int


@dataclass(frozen=True)
class TokenLifetimeMetric:
    """Token lifetime metric payload."""

    provider: str
    ttl_seconds: float


@dataclass(frozen=True)
class TokenRefreshMetric:
    """Token refresh metric payload."""

    provider: str
    result: MetricResult
    duration_seconds: float
    background: bool


@dataclass(frozen=True)
class CacheMetric:
    """Authentication cache metric payload."""

    provider: str
    result: MetricResult | None = None


@dataclass(frozen=True)
class ConfigMetric:
    """Config-reader metric payload."""

    source: str
    result: MetricResult
    duration_seconds: float


@dataclass
class _AuthMetricsCell:
    metrics: AuthMetricsLike


def metric_start() -> float:
    """Return a monotonic start timestamp for metric duration measurement."""

    return monotonic()


def metric_duration_seconds(start: float) -> float:
    """Return elapsed seconds since ``start``."""

    return monotonic() - start


class AuthMetricsRecorder:
    """Small mutable auth metrics recorder with a fixed provider label."""

    def __init__(self, metrics: AuthMetricsLike, provider: str) -> None:
        self._cell: _AuthMetricsCell
        self._cell = (
            metrics._cell
            if isinstance(metrics, AuthMetricsRecorder)
            else _AuthMetricsCell(metrics)
        )
        self.provider = provider

    def set_metrics(self, metrics: AuthMetricsLike) -> None:
        """Replace callbacks, sharing callback state with recorders when given."""

        if isinstance(metrics, AuthMetricsRecorder):
            self._cell = metrics._cell
            return
        self._cell.metrics = metrics

    def token_acquire(
        self, result: MetricResult, duration_seconds: float, attempt: int
    ) -> None:
        """Emit a token acquisition event."""

        emit_metric(
            self._cell.metrics,
            ("token_acquire", "tokenAcquire"),
            TokenAcquireMetric(
                provider=self.provider,
                result=result,
                duration_seconds=duration_seconds,
                attempt=attempt if attempt > 0 else 1,
            ),
        )

    def token_acquire_from_start(
        self,
        result: MetricResult,
        start: float,
        attempt: int,
        token: object | None = None,
    ) -> None:
        """Emit token acquisition duration and optional token lifetime.

        ``start`` must come from :func:`metric_start`. When ``token`` is
        provided for a successful acquisition, its lifetime is emitted too.
        """

        self.token_acquire(result, metric_duration_seconds(start), attempt)
        if result == METRIC_RESULT_SUCCESS and token is not None:
            self.token_lifetime(token)

    def token_lifetime(self, token: object) -> None:
        """Emit token lifetime when the token has an aware expiration timestamp."""

        expiration = getattr(token, "expiration", None)
        if not isinstance(expiration, datetime):
            return
        if expiration.tzinfo is None or expiration.utcoffset() is None:
            return
        try:
            ttl = max((expiration - datetime.now(timezone.utc)).total_seconds(), 0)
        except (OverflowError, TypeError, ValueError):
            return
        emit_metric(
            self._cell.metrics,
            ("token_lifetime", "tokenLifetime"),
            TokenLifetimeMetric(provider=self.provider, ttl_seconds=ttl),
        )

    def token_refresh(
        self,
        result: MetricResult,
        duration_seconds: float,
        background: bool = True,
    ) -> None:
        """Emit a token refresh event."""

        emit_metric(
            self._cell.metrics,
            ("token_refresh", "tokenRefresh"),
            TokenRefreshMetric(
                provider=self.provider,
                result=result,
                duration_seconds=duration_seconds,
                background=background,
            ),
        )

    def cache_hit(self) -> None:
        """Emit a cache hit event."""

        emit_metric(
            self._cell.metrics,
            ("cache_hit", "cacheHit"),
            CacheMetric(provider=self.provider),
        )

    def cache_miss(self, result: MetricResult) -> None:
        """Emit a cache miss event."""

        emit_metric(
            self._cell.metrics,
            ("cache_miss", "cacheMiss"),
            CacheMetric(provider=self.provider, result=result),
        )

    def cache_store(self, result: MetricResult) -> None:
        """Emit a cache store event."""

        emit_metric(
            self._cell.metrics,
            ("cache_store", "cacheStore"),
            CacheMetric(provider=self.provider, result=result),
        )

    def cache_refresh(self, result: MetricResult) -> None:
        """Emit a cache refresh event."""

        emit_metric(
            self._cell.metrics,
            ("cache_refresh", "cacheRefresh"),
            CacheMetric(provider=self.provider, result=result),
        )

    def cache_invalidate(self) -> None:
        """Emit a cache invalidation event."""

        emit_metric(
            self._cell.metrics,
            ("cache_invalidate", "cacheInvalidate"),
            CacheMetric(provider=self.provider),
        )


def auth_metrics_recorder(
    metrics: AuthMetricsLike, provider: str
) -> AuthMetricsRecorder:
    """Create an auth metrics recorder, preserving shared callback cells."""

    return AuthMetricsRecorder(metrics, provider)


def record_config_metric(
    metrics: MetricsLike,
    kind: Literal["config_load", "credentials_resolve"],
    source: str,
    result: MetricResult,
    duration_seconds: float,
) -> None:
    """Emit a config-reader metric."""

    names = (
        ("config_load", "configLoad")
        if kind == "config_load"
        else ("credentials_resolve", "credentialsResolve")
    )
    emit_metric(
        metrics,
        names,
        ConfigMetric(source=source, result=result, duration_seconds=duration_seconds),
    )


def emit_metric(metrics: object | None, names: tuple[str, str], metric: object) -> None:
    """Call a metric callback if present and swallow callback failures."""

    try:
        callback = _metric_callback(metrics, names)
        if callback is None:
            return
        result = callback(metric)
    except (CancelledError, Exception):
        return
    if isawaitable(result):
        _schedule_metric_awaitable(cast(Awaitable[object], result))


def auth_metric_provider(bearer: object | None) -> str:
    """Return an auth provider label from a bearer hook."""

    if bearer is None:
        return "custom"

    try:
        provider = getattr(bearer, "metrics_provider", None)
    except Exception:
        provider = None
    if isinstance(provider, str) and provider:
        return provider
    if callable(provider):
        try:
            resolved = provider()
        except Exception:
            resolved = None
        if isinstance(resolved, str) and resolved:
            return resolved

    module = type(bearer).__module__
    class_name = type(bearer).__qualname__
    return f"{module}.{class_name}"


def bind_auth_metrics(bearer: object, metrics: AuthMetricsLike) -> object:
    """Attach auth metrics to ``bearer`` or return an instrumented wrapper."""

    if metrics is None:
        return bearer
    if _apply_metrics_setter(bearer, metrics):
        return bearer

    if not isinstance(bearer, _TokenBearer):
        return bearer
    return _InstrumentedBearer(
        bearer, auth_metrics_recorder(metrics, auth_metric_provider(bearer))
    )


def _metric_callback(
    metrics: object | None, names: tuple[str, str]
) -> Callable[[object], object] | None:
    if metrics is None:
        return None
    if isinstance(metrics, Mapping):
        for name in names:
            value = metrics.get(name)
            if callable(value):
                return cast(Callable[[object], object], value)
    for name in names:
        value = getattr(metrics, name, None)
        if callable(value):
            return cast(Callable[[object], object], value)
    return None


def _schedule_metric_awaitable(awaitable: Awaitable[object]) -> None:
    try:
        get_running_loop()
    except RuntimeError:
        _run_metric_awaitable(awaitable)
        return
    create_task(_swallow_metric_awaitable(awaitable))


async def _swallow_metric_awaitable(awaitable: Awaitable[object]) -> None:
    try:
        await awaitable
    except (CancelledError, Exception):
        return


def _run_metric_awaitable(awaitable: Awaitable[object]) -> None:
    try:
        asyncio_run(_swallow_metric_awaitable(awaitable))
    except (CancelledError, Exception):
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()


def _apply_metrics_setter(
    bearer: object, metrics: AuthMetricsLike, seen: set[int] | None = None
) -> bool:
    if seen is None:
        seen = set()
    ident = id(bearer)
    if ident in seen:
        return False
    seen.add(ident)

    for name in ("set_metrics", "setMetrics"):
        setter = getattr(bearer, name, None)
        if callable(setter):
            setter(metrics)
            return True

    wrapped = getattr(bearer, "wrapped", None)
    if wrapped is not None:
        return _apply_metrics_setter(wrapped, metrics, seen)
    return False


class _InstrumentedReceiver(_TokenReceiver):
    def __init__(self, receiver: _TokenReceiver, metrics: AuthMetricsRecorder) -> None:
        super().__init__()
        self._receiver = receiver
        self._metrics = metrics
        self._attempt = 0

    @property
    def latest(self) -> _Token | None:
        """Return the wrapped receiver's latest token."""

        latest = getattr(self._receiver, "latest", None)
        return latest if isinstance(latest, _Token) else None

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> _Token:
        self._attempt += 1
        start = metric_start()
        try:
            token = await self._receiver.fetch(timeout=timeout, options=options)
        except Exception:
            self._metrics.token_acquire_from_start(
                METRIC_RESULT_ERROR, start, self._attempt
            )
            raise
        if not isinstance(token, _Token):
            self._metrics.token_acquire_from_start(
                METRIC_RESULT_ERROR, start, self._attempt
            )
            raise TypeError(f"Expected Token from receiver, got {type(token)}")
        self._metrics.token_acquire_from_start(
            METRIC_RESULT_SUCCESS, start, self._attempt, token
        )
        return token

    async def fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> _Token:
        """Fetch a token and record the result."""

        return await super().fetch(timeout=timeout, options=options)

    def can_retry(self, err: Exception, options: dict[str, str] | None = None) -> bool:
        """Delegate retry decisions to the wrapped receiver."""

        return bool(self._receiver.can_retry(err, options))


class _InstrumentedBearer(_TokenBearer):
    def __init__(self, bearer: _TokenBearer, metrics: AuthMetricsRecorder) -> None:
        self._bearer = bearer
        self._metrics = metrics

    @property
    def name(self) -> str | None:
        """Return the wrapped bearer's name."""

        name = getattr(self._bearer, "name", None)
        return name if isinstance(name, str) else None

    @property
    def wrapped(self) -> _TokenBearer:
        """Return the wrapped bearer."""

        return self._bearer

    @property
    def metrics_provider(self) -> str:
        """Return the metric provider label."""

        return self._metrics.provider

    def receiver(self) -> _InstrumentedReceiver:
        """Return an instrumented receiver."""

        return _InstrumentedReceiver(self._bearer.receiver(), self._metrics)

    def set_metrics(self, metrics: AuthMetricsLike) -> None:
        """Replace callbacks and propagate them to the wrapped bearer."""

        self._metrics.set_metrics(metrics)
        bind_auth_metrics(self._bearer, self._metrics)

    async def close(self, grace: float | None = None) -> None:
        """Close the wrapped bearer."""

        close = getattr(self._bearer, "close", None)
        if callable(close):
            await close(grace=grace)
