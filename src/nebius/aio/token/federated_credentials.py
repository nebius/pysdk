from datetime import timedelta

from nebius.aio.base import ChannelBase
from nebius.aio.token.deferred_channel import DeferredChannel
from nebius.aio.token.exchangeable import Bearer as ExchangeableBearer
from nebius.aio.token.renewable import Bearer as RenewableBearer
from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import NamedBearer, Receiver
from nebius.base.service_account.federated_credentials import (
    FederatedCredentialsBearer as FederatedCredentialsReader,
)
from nebius.base.service_account.federated_credentials import (
    FederatedCredentialsTokenRequester,
    FileFederatedCredentials,
)


class FederatedCredentialsBearer(ParentBearer):
    def __init__(
        self,
        federated_credentials: (
            FederatedCredentialsTokenRequester | FederatedCredentialsReader | str
        ),
        service_account_id: str | None = None,
        channel: ChannelBase | DeferredChannel | None = None,
        max_retries: int = 2,
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        refresh_request_timeout: timedelta = timedelta(seconds=5),
    ) -> None:
        if isinstance(federated_credentials, str):
            federated_credentials = FileFederatedCredentials(federated_credentials)
        if isinstance(federated_credentials, FederatedCredentialsReader):
            if not isinstance(service_account_id, str):
                raise TypeError(
                    "Service account ID must be provided as a string when "
                    "federated_credentials is a string."
                )
            federated_credentials = FederatedCredentialsTokenRequester(
                service_account_id=service_account_id,
                credentials=federated_credentials,
            )

        if not isinstance(federated_credentials, FederatedCredentialsTokenRequester):  # type: ignore[unused-ignore]
            raise TypeError(
                "federated_credentials must be FederatedCredentialsTokenRequester, "
                "FederatedCredentialsBearer or string"
                f", got {type(federated_credentials)}"
            )

        self._exchangeable = ExchangeableBearer(
            federated_credentials,
            channel=channel,
            max_retries=max_retries,
        )
        self._source: ParentBearer = RenewableBearer(
            self._exchangeable,
            max_retries=max_retries,
            lifetime_safe_fraction=lifetime_safe_fraction,
            initial_retry_timeout=initial_retry_timeout,
            max_retry_timeout=max_retry_timeout,
            retry_timeout_exponent=retry_timeout_exponent,
            refresh_request_timeout=refresh_request_timeout,
        )

        if isinstance(federated_credentials.credentials, FileFederatedCredentials):
            self._source = NamedBearer(
                self._source,
                f"federated-credentials/{federated_credentials.service_account_id}"
                f"/{federated_credentials.credentials.file_path}",
            )

    def set_channel(self, channel: ChannelBase) -> None:
        self._exchangeable.set_channel(channel)

    @property
    def wrapped(self) -> "ParentBearer|None":
        return self._source

    def receiver(self) -> "Receiver":
        return self._source.receiver()
