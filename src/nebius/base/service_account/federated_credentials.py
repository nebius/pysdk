from abc import ABC, abstractmethod

from nebius.api.nebius.iam.v1 import ExchangeTokenRequest
from nebius.base.service_account.service_account import TokenRequester


class FederatedCredentialsBearer(ABC):
    @abstractmethod
    def credentials(self) -> str:
        raise NotImplementedError("Method not implemented!")


class FederatedCredentialsTokenRequester(TokenRequester):
    def __init__(
        self, service_account_id: str, credentials: FederatedCredentialsBearer
    ) -> None:
        self.service_account_id = service_account_id
        self.credentials = credentials
        super().__init__()

    def get_exchange_token_request(self) -> ExchangeTokenRequest:
        return ExchangeTokenRequest(
            grant_type="urn:ietf:params:oauth:grant-type:token-exchange",
            requested_token_type="urn:ietf:params:oauth:token-type:access_token",  # noqa: S106
            subject_token=self.service_account_id,
            subject_token_type="urn:nebius:params:oauth:token-type:subject_identifier",  # noqa: S106
            actor_token_type="urn:ietf:params:oauth:token-type:jwt",  # noqa: S106
            actor_token=self.credentials.credentials(),
        )


class StaticFederatedCredentials(FederatedCredentialsBearer):
    def __init__(self, credentials: str) -> None:
        self._credentials = credentials

    def credentials(self) -> str:
        return self._credentials


class FileFederatedCredentials(FederatedCredentialsBearer):
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def credentials(self) -> str:
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
