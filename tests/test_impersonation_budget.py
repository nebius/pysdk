from datetime import timedelta

import pytest
from nebius.aio.token.federation_account import FederationBearer
from nebius.aio.token.federation_bearer import Bearer as FederationAuthBearer
from nebius.aio.token.federation_bearer.auth import DEFAULT_LOGIN_TIMEOUT
from nebius.aio.token.impersonated import EXCHANGE_ALLOWANCE
from nebius.aio.token.impersonated import CachedBearer as ImpersonatedBearer
from nebius.aio.token.renewable import DEFAULT_REFRESH_REQUEST_TIMEOUT
from nebius.aio.token.renewable import Bearer as RenewableBearer
from nebius.aio.token.static import Bearer as StaticBearer
from nebius.aio.token.token import Bearer, NamedBearer, Receiver, Token
from nebius.api.nebius.iam.v1 import CreateTokenResponse, ExchangeTokenRequest

SERVICE_ACCOUNT_ID = "serviceaccount-e0target"
FEDERATION_ARGS = ("profile", "client", "auth.example.test", "federation-id")


class InstantReceiver(Receiver):
    async def _fetch(self, timeout: float | None = None, options: dict[str, str] | None = None) -> Token:
        return Token("actor")

    def can_retry(self, err: Exception, options: dict[str, str] | None = None) -> bool:
        return False


class BudgetBearer(Bearer):
    """Custom provider with its own budget. It is not a federation bearer."""

    def __init__(self, budget: timedelta | None) -> None:
        self.budget = budget

    @property
    def acquisition_budget(self) -> timedelta | None:
        return self.budget

    def receiver(self) -> Receiver:
        return InstantReceiver()


class RecordingExchange:
    def __init__(self) -> None:
        self.timeouts: list[float | None] = []

    async def exchange(
        self,
        request: ExchangeTokenRequest,
        timeout: float | None = None,
        auth_options: dict[str, str] | None = None,
    ) -> CreateTokenResponse:
        self.timeouts.append(timeout)
        return CreateTokenResponse(
            access_token="imp_" + request.subject_token,
            token_type="Bearer",
            expires_in=3600,
        )


def budget_of(bearer: ImpersonatedBearer) -> timedelta:
    renewable = bearer.wrapped.wrapped  # NamedBearer wraps the renewable cache.
    assert isinstance(renewable, RenewableBearer)
    return renewable.refresh_request_timeout


async def fetch_with_exchange(bearer: ImpersonatedBearer) -> list[float | None]:
    exchange = RecordingExchange()
    bearer._impersonated._svc = exchange  # The unit test has no gRPC channel.
    try:
        token = await bearer.receiver().fetch(timeout=5)
        assert token.token == "imp_" + SERVICE_ACCOUNT_ID
    finally:
        await bearer.close()
    return exchange.timeouts


@pytest.mark.asyncio()
async def test_custom_provider_budget_reaches_the_exchange() -> None:
    bearer = ImpersonatedBearer(SERVICE_ACCOUNT_ID, BudgetBearer(timedelta(seconds=42)))
    assert await fetch_with_exchange(bearer) == [(timedelta(seconds=42) + EXCHANGE_ALLOWANCE).total_seconds()]


@pytest.mark.asyncio()
async def test_budget_is_read_on_each_fetch() -> None:
    provider = BudgetBearer(timedelta(seconds=7))
    bearer = ImpersonatedBearer(SERVICE_ACCOUNT_ID, provider)
    provider.budget = timedelta(seconds=9)
    assert await fetch_with_exchange(bearer) == [(timedelta(seconds=9) + EXCHANGE_ALLOWANCE).total_seconds()]


def test_explicit_budget_wins_and_zero_is_exact() -> None:
    bearer = ImpersonatedBearer(
        SERVICE_ACCOUNT_ID,
        BudgetBearer(timedelta(seconds=42)),
        refresh_request_timeout=timedelta(0),
    )
    assert budget_of(bearer) == timedelta(0)


@pytest.mark.parametrize(
    "source",
    [StaticBearer("actor"), BudgetBearer(None), BudgetBearer(timedelta(0)), BudgetBearer(timedelta(seconds=-1))],
    ids=["no contract", "no budget", "zero", "negative"],
)
def test_source_without_a_positive_budget_keeps_the_default(source: Bearer) -> None:
    bearer = ImpersonatedBearer(SERVICE_ACCOUNT_ID, source)
    assert budget_of(bearer) == DEFAULT_REFRESH_REQUEST_TIMEOUT


def test_federation_budget_is_the_configured_login_timeout() -> None:
    federation = FederationBearer(*FEDERATION_ARGS, timeout=timedelta(seconds=7))
    assert federation.acquisition_budget == timedelta(seconds=7)
    bearer = ImpersonatedBearer(SERVICE_ACCOUNT_ID, federation)
    assert budget_of(bearer) == timedelta(seconds=7) + EXCHANGE_ALLOWANCE


def test_bare_federation_bearer_reports_the_default_login_timeout() -> None:
    bearer = ImpersonatedBearer(SERVICE_ACCOUNT_ID, FederationAuthBearer(*FEDERATION_ARGS))
    assert budget_of(bearer) == timedelta(seconds=DEFAULT_LOGIN_TIMEOUT) + EXCHANGE_ALLOWANCE


def test_transparent_wrappers_forward_the_budget() -> None:
    provider = BudgetBearer(timedelta(seconds=7))
    assert NamedBearer(provider, "named").acquisition_budget == timedelta(seconds=7)
    assert (
        ImpersonatedBearer(SERVICE_ACCOUNT_ID, provider).acquisition_budget == timedelta(seconds=7) + EXCHANGE_ALLOWANCE
    )


def test_renewable_cap_is_reported_outward() -> None:
    renewable = RenewableBearer(BudgetBearer(timedelta(seconds=42)), refresh_request_timeout=timedelta(seconds=3))
    assert renewable.acquisition_budget == timedelta(seconds=3)
    assert budget_of(ImpersonatedBearer(SERVICE_ACCOUNT_ID, renewable)) == timedelta(seconds=3) + EXCHANGE_ALLOWANCE


def test_overflow_saturates() -> None:
    bearer = ImpersonatedBearer(SERVICE_ACCOUNT_ID, BudgetBearer(timedelta.max))
    assert budget_of(bearer) == timedelta.max
