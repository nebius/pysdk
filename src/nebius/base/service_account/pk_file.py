from logging import getLogger

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
        filename: str,
        public_key_id: str,
        service_account_id: str,
    ) -> None:
        self._fn = filename
        self._kid = public_key_id
        self._said = service_account_id

    def read(self) -> ServiceAccount:
        log.debug(f"reading SA from file {self._fn}")
        with open(self._fn, "rb") as f:
            pk = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        if not isinstance(pk, RSAPrivateKey):
            raise WrongKeyTypeError(pk)
        return ServiceAccount(pk, self._kid, self._said)
