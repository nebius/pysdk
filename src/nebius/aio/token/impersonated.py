"""Bearer for service-account impersonation via token exchange."""

from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import cast

from grpc import StatusCode

from nebius.aio.abc import ClientChannelInterface
from nebius.aio.authorization.options import OPTION_TYPE, Types
from nebius.aio.metrics import (
    METRIC_RESULT_ERROR,
    METRIC_RESULT_SUCCESS,
    AuthMetricsLike,
    AuthMetricsRecorder,
    auth_metrics_recorder,
    bind_auth_metrics,
    metric_start,
)
from nebius.aio.service_error import RequestError
from nebius.aio.token.deferred_channel import DeferredChannel
from nebius.api.nebius.iam.v1 import (
    CreateTokenResponse,
    ExchangeTokenRequest,
    TokenExchangeServiceClient,
)
from nebius.base.error import SDKError
from nebius.base.token_sanitizer import TokenSanitizer

from .exchangeable import UnsupportedResponseError, UnsupportedTokenTypeError
from .options import OPTION_MAX_RETRIES
from .token import Bearer as ParentBearer
from .token import NamedBearer, Token
from .token import Receiver as ParentReceiver

TOKEN_EXCHANGE_ACCESS_TOKEN_TYPE = (
    "urn:ietf:params:oauth:token-type:access_token"  # noqa: S105
)
TOKEN_EXCHANGE_GRANT_TYPE = (
    "urn:ietf:params:oauth:grant-type:token-exchange"  # noqa: S105
)
TOKEN_EXCHANGE_SUBJECT_IDENTIFIER_TYPE = (
    "urn:nebius:params:oauth:token-type:subject_identifier"  # noqa: S105
)

sanitizer = TokenSanitizer.access_token_sanitizer()
log = getLogger(__name__)


class Receiver(ParentReceiver):
    """Receiver that exchanges an actor token for an impersonated token."""

    def __init__(
        self,
        service_account_id: str,
        source: ParentReceiver,
        service: TokenExchangeServiceClient | Awaitable[TokenExchangeServiceClient],
        max_retries: int = 2,
        metrics: AuthMetricsLike = None,
    ) -> None:
        """Create a receiver bound to the source token receiver."""
        super().__init__()
        self._service_account_id = service_account_id
        self._source = source
        self._svc = service
        self._max_retries = max_retries
        self._metrics = auth_metrics_recorder(metrics, "impersonated")
        self._trial = 0

    async def _fetch(
        self, timeout: float | None = None, options: dict[str, str] | None = None
    ) -> Token:
        """Fetch the source token and exchange it for an impersonated token."""
        self._trial += 1
        start = metric_start()
        try:
            actor = await self._source.fetch(timeout=timeout, options=options)
            now = datetime.now(timezone.utc)
            try:
                token = await self._exchange(actor.token, now, timeout)
            except RequestError as err:
                if not self._should_retry_actor(err, options):
                    raise
                actor = await self._source.fetch(timeout=timeout, options=options)
                now = datetime.now(timezone.utc)
                token = await self._exchange(actor.token, now, timeout)
        except Exception:
            self._metrics.token_acquire_from_start(
                METRIC_RESULT_ERROR,
                start,
                self._trial,
            )
            raise
        self._metrics.token_acquire_from_start(
            METRIC_RESULT_SUCCESS,
            start,
            self._trial,
            token,
        )
        return token

    async def _exchange(
        self,
        actor_token: str,
        now: datetime,
        timeout: float | None,
    ) -> Token:
        """Exchange ``actor_token`` for the configured service account token."""
        if isinstance(self._svc, Awaitable):
            self._svc = await self._svc
        request = ExchangeTokenRequest(
            grant_type=TOKEN_EXCHANGE_GRANT_TYPE,
            requested_token_type=TOKEN_EXCHANGE_ACCESS_TOKEN_TYPE,
            subject_token=self._service_account_id,
            subject_token_type=TOKEN_EXCHANGE_SUBJECT_IDENTIFIER_TYPE,
            actor_token=actor_token,
            actor_token_type=TOKEN_EXCHANGE_ACCESS_TOKEN_TYPE,
        )
        response = await self._svc.exchange(
            request,
            timeout=timeout,
            auth_options={OPTION_TYPE: Types.DISABLE},
        )
        if not isinstance(response, CreateTokenResponse):
            raise UnsupportedResponseError(CreateTokenResponse.__name__, response)
        if response.token_type != "Bearer":  # noqa: S105 - protocol token type
            raise UnsupportedTokenTypeError(response.token_type)
        log.debug(
            "impersonated token fetched: %s, expires in: %s seconds.",
            sanitizer.sanitize(response.access_token),
            response.expires_in,
        )
        return Token(
            token=response.access_token,
            expiration=now + timedelta(seconds=response.expires_in),
        )

    def _should_retry_actor(
        self,
        err: RequestError,
        options: dict[str, str] | None,
    ) -> bool:
        code = err.status.code
        return code == StatusCode.UNAUTHENTICATED and self._source.can_retry(
            err,
            options,
        )

    def can_retry(
        self,
        err: Exception,
        options: dict[str, str] | None = None,
    ) -> bool:
        """Allow the request layer to retry a failed impersonation fetch."""
        max_retries = self._max_retries
        if options is not None and OPTION_MAX_RETRIES in options:
            try:
                max_retries = int(options[OPTION_MAX_RETRIES])
            except ValueError as val_err:
                log.error(
                    "option %s is not valid integer: %s",
                    OPTION_MAX_RETRIES,
                    val_err,
                )
        return self._trial < max_retries


class Bearer(ParentBearer):
    """Bearer that creates receivers for exchange-based impersonation."""

    def __init__(
        self,
        service_account_id: str,
        source: ParentBearer,
        channel: ClientChannelInterface | DeferredChannel | None = None,
        max_retries: int = 2,
        metrics: AuthMetricsLike = None,
    ) -> None:
        """Create an impersonation bearer."""
        if service_account_id == "":
            raise SDKError("service account id must not be empty")
        super().__init__()
        self._service_account_id = service_account_id
        self._max_retries = max_retries
        self._metrics: AuthMetricsRecorder = auth_metrics_recorder(
            metrics,
            "impersonated",
        )
        self._source = cast(ParentBearer, bind_auth_metrics(source, self._metrics))
        if not isinstance(self._source, ParentBearer):  # type: ignore[unused-ignore]
            raise TypeError(f"Expected token bearer, got {type(source)}")
        self._svc: TokenExchangeServiceClient | None = None
        self._deferred_channel: DeferredChannel | None = None
        self.set_channel(channel)

    @property
    def wrapped(self) -> ParentBearer | None:
        """Return the actor token bearer."""
        return self._source

    @property
    def name(self) -> str | None:
        """Return a cache-friendly name for this impersonation chain."""
        source_name = self._source.name or "anonymous"
        return f"impersonated/{self._service_account_id}/{source_name}"

    @property
    def metrics_provider(self) -> str:
        """Return the auth metric provider label."""
        return self._metrics.provider

    def set_channel(
        self,
        channel: ClientChannelInterface | DeferredChannel | None,
    ) -> None:
        """Set the channel used for token exchange RPCs."""
        if isinstance(channel, Awaitable):  # type: ignore[unused-ignore]
            self._deferred_channel = channel
            self._svc = None
        elif channel is not None:
            self._deferred_channel = None
            self._svc = TokenExchangeServiceClient(channel)
        else:
            self._deferred_channel = None
            self._svc = None

    async def _token_exchange_service_stub(self) -> TokenExchangeServiceClient:
        if self._deferred_channel is None:
            raise ValueError("gRPC channel is not set for the bearer.")
        channel = await self._deferred_channel
        if not isinstance(channel, ClientChannelInterface):  # type: ignore[unused-ignore]
            raise TypeError(f"Expected ClientChannelInterface, got {type(channel)}.")
        self._svc = TokenExchangeServiceClient(channel)
        return self._svc

    def receiver(self) -> Receiver:
        """Return a receiver that exchanges the actor token."""
        if self._svc is None and self._deferred_channel is None:
            raise ValueError("gRPC channel is not set for the bearer.")
        service: TokenExchangeServiceClient | Awaitable[TokenExchangeServiceClient]
        if self._svc is None:
            service = self._token_exchange_service_stub()
        else:
            service = self._svc
        return Receiver(
            self._service_account_id,
            self._source.receiver(),
            service,
            max_retries=self._max_retries,
            metrics=self._metrics,
        )

    def set_metrics(self, metrics: AuthMetricsLike) -> None:
        """Attach auth metrics callbacks and propagate them to the actor bearer."""
        self._metrics.set_metrics(metrics)
        self._source = cast(
            ParentBearer,
            bind_auth_metrics(self._source, self._metrics),
        )


class CachedBearer(ParentBearer):
    """Convenience wrapper that caches impersonated tokens in memory."""

    def __init__(
        self,
        service_account_id: str,
        source: ParentBearer,
        channel: ClientChannelInterface | DeferredChannel | None = None,
        max_retries: int = 2,
        metrics: AuthMetricsLike = None,
    ) -> None:
        """Create a cached impersonation bearer."""
        from nebius.aio.token.renewable import Bearer as RenewableBearer

        self._impersonated = Bearer(
            service_account_id,
            source,
            channel=channel,
            max_retries=max_retries,
            metrics=metrics,
        )
        self._source = NamedBearer(
            RenewableBearer(
                self._impersonated,
                max_retries=max_retries,
                metrics=metrics,
                provider="impersonated",
            ),
            self._impersonated.name or f"impersonated/{service_account_id}",
        )

    @property
    def wrapped(self) -> ParentBearer | None:
        """Return the cached bearer chain."""
        return self._source

    def receiver(self) -> ParentReceiver:
        """Return a receiver from the cached bearer chain."""
        return self._source.receiver()

    def set_metrics(self, metrics: AuthMetricsLike) -> None:
        """Attach auth metrics callbacks to the chain."""
        self._impersonated.set_metrics(metrics)
        wrapped = self._source.wrapped
        setter = getattr(wrapped, "set_metrics", None)
        if callable(setter):
            setter(metrics)
