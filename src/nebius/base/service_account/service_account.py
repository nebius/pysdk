from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from nebius.api.nebius.iam.v1.token_service_pb2 import ExchangeTokenRequest

log = getLogger(__name__)


class TokenRequester(ABC):
    @abstractmethod
    def get_exchange_token_request(self) -> ExchangeTokenRequest:
        raise NotImplementedError("Method not implemented!")


class ServiceAccount(TokenRequester):
    def __init__(
        self,
        private_key: RSAPrivateKey,
        public_key_id: str,
        service_account_id: str,
    ) -> None:
        self._pk = private_key
        self._kid = public_key_id
        self._said = service_account_id

    @property
    def private_key(self) -> RSAPrivateKey:
        return self._pk

    @property
    def public_key_id(self) -> str:
        return self._kid

    @property
    def service_account_id(self) -> str:
        return self._said

    def get_exchange_token_request(self) -> ExchangeTokenRequest:
        now = datetime.now(tz=timezone.utc)
        jwt_ttl = timedelta(minutes=1)

        # Create JWT claims
        claims: dict[str, Any] = {
            "iss": self.service_account_id,
            "sub": self.service_account_id,
            "aud": "token-service.iam.new.nebiuscloud.net",
            "exp": now + jwt_ttl,
            "iat": now,
        }

        # Create the JWT token and sign it with RS256
        headers = {"kid": self.public_key_id}
        signed_jwt = jwt.encode(
            claims, self.private_key, algorithm="RS256", headers=headers
        )
        log.debug("creating ExchangeTokenRequest for service account")

        # Return the ExchangeTokenRequest object
        return ExchangeTokenRequest(
            grant_type="urn:ietf:params:oauth:grant-type:token-exchange",
            requested_token_type="urn:ietf:params:oauth:token-type:access_token",  # noqa: S106 - not a password
            subject_token=signed_jwt,
            subject_token_type="urn:ietf:params:oauth:token-type:jwt",  # noqa: S106 - not a password
        )


class Reader(TokenRequester):
    @abstractmethod
    def read(self) -> ServiceAccount:
        raise NotImplementedError("Method not implemented!")

    def get_exchange_token_request(self) -> ExchangeTokenRequest:
        return self.read().get_exchange_token_request()
