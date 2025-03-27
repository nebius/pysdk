from logging import getLogger
from typing import TypeVar

from grpc.aio._metadata import Metadata as GRPCMetadata

from nebius.base.metadata import Internal, Metadata

log = getLogger(__name__)

MD = TypeVar("MD", Metadata, GRPCMetadata)


def get_options_from_metadata(metadata: MD | None) -> dict[str, str]:
    ret = dict[str, str]()
    if metadata is None:
        return ret
    if isinstance(metadata, GRPCMetadata):
        selected_options = metadata.get_all(Internal.AUTHORIZATION_OPTION.lower())
    elif isinstance(metadata, Metadata):  # type: ignore[unused-ignore]
        selected_options = metadata[Internal.AUTHORIZATION_OPTION]
    for option in selected_options:
        if isinstance(option, bytes):
            option = option.decode("utf-8")
        if isinstance(option, str):
            k, v = option.split("=", 1)
            ret[k] = v
        else:
            log.error(f"invalid auth option type {type(option)}")
    return ret


def add_options_to_metadata(options: dict[str, str], metadata: MD) -> MD:
    for k, v in options.items():
        if "=" in k:
            raise ValueError(f"option key contains '=' {k}")
        metadata.add(Internal.AUTHORIZATION_OPTION.lower(), k + "=" + v)
    return metadata


def options_to_metadata(options: dict[str, str]) -> Metadata:
    return add_options_to_metadata(options, Metadata())
