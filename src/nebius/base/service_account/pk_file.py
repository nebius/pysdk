from logging import getLogger
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes

from .service_account import Reader as BaseReader
from .service_account import ServiceAccount

log = getLogger(__name__)


class WrongKeyTypeError(Exception):
    def __init__(self, pk: PrivateKeyTypes) -> None:
        super().__init__(f"Wrong key type {type(pk)}")


class Reader(BaseReader):
    def __init__(
        self,
        filename: str | Path,
        public_key_id: str,
        service_account_id: str,
    ) -> None:
        filename = Path(filename).expanduser()

        log.debug(f"reading SA from file {filename}")
        with open(filename, "rb") as f:
            pk = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        if not isinstance(pk, RSAPrivateKey):
            raise WrongKeyTypeError(pk)
        self._pk = pk
        self._kid = public_key_id
        self._said = service_account_id

    def read(self) -> ServiceAccount:
        return ServiceAccount(self._pk, self._kid, self._said)
