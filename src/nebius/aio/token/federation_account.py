from datetime import timedelta
from ssl import SSLContext
from typing import TextIO

from nebius.aio.token.token import Bearer as ParentBearer
from nebius.aio.token.token import Receiver

from .federation_bearer import Bearer as FederationAuthBearer
from .file_cache.async_renewable_bearer import AsynchronousRenewableFileCacheBearer


class FederationBearer(ParentBearer):
    def __init__(
        self,
        profile_name: str,
        client_id: str,
        federation_endpoint: str,
        federation_id: str,
        writer: TextIO | None = None,
        no_browser_open: bool = False,
        timeout: timedelta = timedelta(minutes=5),
        max_retries: int = 2,
        initial_safety_margin: timedelta | float | None = timedelta(hours=2),
        retry_safety_margin: timedelta = timedelta(hours=2),
        lifetime_safe_fraction: float = 0.9,
        initial_retry_timeout: timedelta = timedelta(seconds=1),
        max_retry_timeout: timedelta = timedelta(minutes=1),
        retry_timeout_exponent: float = 1.5,
        file_cache_throttle: timedelta | float = timedelta(minutes=5),
        ssl_ctx: SSLContext | None = None,
    ) -> None:
        self._source = AsynchronousRenewableFileCacheBearer(
            FederationAuthBearer(
                profile_name=profile_name,
                client_id=client_id,
                federation_endpoint=federation_endpoint,
                federation_id=federation_id,
                writer=writer,
                no_browser_open=no_browser_open,
                ssl_ctx=ssl_ctx,
            ),
            max_retries=max_retries,
            initial_safety_margin=initial_safety_margin,
            retry_safety_margin=retry_safety_margin,
            lifetime_safe_fraction=lifetime_safe_fraction,
            initial_retry_timeout=initial_retry_timeout,
            max_retry_timeout=max_retry_timeout,
            retry_timeout_exponent=retry_timeout_exponent,
            refresh_request_timeout=timeout,
            file_cache_throttle=file_cache_throttle,
        )

    @property
    def wrapped(self) -> "ParentBearer|None":
        return self._source

    def receiver(self) -> "Receiver":
        return self._source.receiver()
