from datetime import timedelta

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from nebius.aio.base import ChannelBase
from nebius.aio.token.deferred_channel import DeferredChannel
from nebius.aio.token.exchangeable import Bearer as ExchangeableBearer
from nebius.aio.token.renewable import Bearer as RenewableBearer
from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import NamedBearer, Receiver
from nebius.base.service_account.service_account import (
    Reader as ServiceAccountReader,
)
from nebius.base.service_account.service_account import (
    ServiceAccount,
)
from nebius.base.service_account.static import Reader as ServiceAccountReaderStatic


class ServiceAccountBearer(ParentBearer):
    def __init__(
        self,
        service_account: ServiceAccountReader | ServiceAccount | str,
        channel: ChannelBase | DeferredChannel | None = None,
        private_key: RSAPrivateKey | None = None,
        public_key_id: str | None = None,
        max_retries: int = 2,
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        refresh_request_timeout: timedelta = timedelta(seconds=5),
    ) -> None:
        reader: ServiceAccountReader | None = None
        if isinstance(service_account, ServiceAccountReader):
            reader = service_account
            service_account = service_account.read()
        if isinstance(service_account, str):
            if not isinstance(private_key, RSAPrivateKey):
                raise TypeError(
                    "Private key must be provided as RSAPrivateKey instance "
                    "when service_account is a string."
                )
            if not isinstance(public_key_id, str):
                raise TypeError(
                    "Public key ID must be provided as a string when service_account "
                    "is a string."
                )
            service_account = ServiceAccount(
                private_key=private_key,
                public_key_id=public_key_id,
                service_account_id=service_account,
            )
        else:
            if private_key is not None or public_key_id is not None:
                raise ValueError(
                    "Private key and public key ID must not be provided "
                    "when service_account is a ServiceAccount or ServiceAccountReader "
                    "instance."
                )
        if not isinstance(service_account, ServiceAccount):  # type: ignore[unused-ignore]
            raise TypeError(
                "service_account must be ServiceAccountReader, ServiceAccount or string"
                f", got {type(service_account)}"
            )
        if reader is None:
            reader = ServiceAccountReaderStatic(service_account)
        sa_id = service_account.service_account_id
        public_key_id = service_account.public_key_id
        private_key = service_account.private_key

        self._exchangeable = ExchangeableBearer(
            reader,
            channel=channel,
            max_retries=max_retries,
        )

        self._source = NamedBearer(
            RenewableBearer(
                self._exchangeable,
                max_retries=max_retries,
                lifetime_safe_fraction=lifetime_safe_fraction,
                initial_retry_timeout=initial_retry_timeout,
                max_retry_timeout=max_retry_timeout,
                retry_timeout_exponent=retry_timeout_exponent,
                refresh_request_timeout=refresh_request_timeout,
            ),
            f"service-account/{sa_id}/{public_key_id}",
        )

    def set_channel(self, channel: ChannelBase) -> None:
        self._exchangeable.set_channel(channel)

    @property
    def wrapped(self) -> "ParentBearer|None":
        return self._source

    def receiver(self) -> "Receiver":
        return self._source.receiver()
