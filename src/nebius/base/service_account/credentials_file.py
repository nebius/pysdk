import json
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from .pk_file import WrongKeyTypeError
from .service_account import Reader as BaseReader
from .service_account import ServiceAccount

log = getLogger(__name__)


@dataclass
class SubjectCredentials:
    type: str
    alg: str
    private_key: str
    kid: str
    iss: str
    sub: str

    def validate(self) -> None:
        if self.type != "" and self.type != "JWT":
            raise ValueError(
                f"Invalid service account credentials type: '{self.type}',"
                " only 'JWT' is supported."
            )

        if self.alg != "RS256":
            raise ValueError(
                f"Invalid service account algorithm: '{self.alg}',"
                " only 'RS256' is supported."
            )

        if self.iss != self.sub:
            raise ValueError(
                f"Issuer must be the same as subject: '{self.iss}' != '{self.sub}'."
            )

    def parse_private_key(self) -> RSAPrivateKey:
        pk = serialization.load_pem_private_key(
            self.private_key.encode("utf-8"), password=None, backend=default_backend()
        )

        if not isinstance(pk, RSAPrivateKey):
            raise WrongKeyTypeError(pk)
        return pk


@dataclass
class ServiceAccountCredentials:
    subject_credentials: SubjectCredentials

    @staticmethod
    def from_json(data: dict[str, Any]) -> "ServiceAccountCredentials":
        subject_data = data["subject-credentials"]
        subject_credentials = SubjectCredentials(
            type=subject_data["type"] if "type" in subject_data else "",
            alg=subject_data["alg"],
            private_key=subject_data["private-key"],
            kid=subject_data["kid"],
            iss=subject_data["iss"],
            sub=subject_data["sub"],
        )
        subject_credentials.validate()
        return ServiceAccountCredentials(subject_credentials)


class Reader(BaseReader):
    def __init__(
        self,
        filename: str | Path,
    ) -> None:
        filename = Path(filename).expanduser()

        log.debug(f"reading SA from Credentials file: {filename}")
        with open(filename, "rb") as f:
            data = json.load(f)
        self._credentials = ServiceAccountCredentials.from_json(data)
        self._parsed_key = self._credentials.subject_credentials.parse_private_key()

    def read(self) -> ServiceAccount:
        return ServiceAccount(
            self._parsed_key,
            self._credentials.subject_credentials.kid,
            self._credentials.subject_credentials.sub,
        )
