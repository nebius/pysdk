from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from grpc import RpcError, Status, StatusCode

from nebius.api.google.protobuf import Any as AnyPb
from nebius.api.google.rpc import Status as StatusPb
from nebius.api.nebius.common.v1 import ServiceError as ServiceErrorPb

_STATUS_DETAILS_KEY = "grpc-status-details-bin"


@dataclass(frozen=True)
class _Status(Status):
    code: StatusCode
    details: str
    trailing_metadata: tuple[tuple[str, bytes], ...]


def _status_code(code: int) -> StatusCode:
    for candidate in StatusCode:
        if candidate.value[0] == code:
            return candidate
    raise ValueError(f"invalid gRPC status code {code}")


def _rich_status_from_call(call: RpcError) -> StatusPb | None:
    raw_metadata = call.trailing_metadata()
    if raw_metadata is None:
        return None
    metadata = cast(Iterable[tuple[str, str | bytes]], raw_metadata)
    for key, value in metadata:
        if key != _STATUS_DETAILS_KEY:
            continue
        if not isinstance(value, bytes):
            raise TypeError("grpc-status-details-bin value must be bytes")
        status = StatusPb.FromString(value)
        call_code = call.code()
        if call_code.value[0] != status.code:
            raise ValueError(
                f"Code in Status proto ({_status_code(status.code)}) "
                f"doesn't match status code ({call_code})"
            )
        call_details = call.details()
        if call_details != status.message:
            raise ValueError(
                f"Message in Status proto ({status.message}) doesn't match "
                f"status details ({call_details})"
            )
        return status
    return None


def pb2_from_status(
    status: StatusPb,
    remove_from_details: bool = False,
) -> list[ServiceErrorPb]:
    """Extract namespace-local service errors from a direct rich status."""
    ret: list[ServiceErrorPb] = []
    rest: list[AnyPb] = []
    registry = type(status).__REGISTRY__
    for detail in status.details:
        try:
            unpacked = registry.unpack_any(detail)
        except LookupError:
            unpacked = None
        if isinstance(unpacked, ServiceErrorPb):
            ret.append(unpacked)
        elif remove_from_details:
            rest.append(detail)
    if remove_from_details:
        status.details = rest
    return ret


def pb2_from_error(err: RpcError) -> list[ServiceErrorPb]:
    status = _rich_status_from_call(err)
    if status is None:
        return []
    return pb2_from_status(status)


def to_anypb(err: ServiceErrorPb) -> AnyPb:
    return type(err).__REGISTRY__.pack_any(err)  # type: ignore[return-value]


def pbrpc_status_of_errors(
    code: int,
    message: str,
    errors: ServiceErrorPb | Iterable[ServiceErrorPb],
) -> StatusPb:
    if isinstance(errors, ServiceErrorPb):
        errors = [errors]
    if isinstance(code, StatusCode):
        code = code.value[0]
    elif isinstance(code, tuple) and isinstance(code[0], int):
        code = code[0]
    return StatusPb(
        code=code,
        message=message,
        details=[to_anypb(error) for error in errors],
    )


def grpc_status_of_errors(
    code: int,
    message: str,
    errors: ServiceErrorPb | Iterable[ServiceErrorPb],
) -> Status:
    status = pbrpc_status_of_errors(code, message, errors)
    return _Status(
        code=_status_code(status.code),
        details=status.message,
        trailing_metadata=((_STATUS_DETAILS_KEY, status.SerializeToString()),),
    )


Metadata = tuple[
    tuple[str, str | bytes],
    ...,
]


def trailing_metadata_of_errors(
    errors: ServiceErrorPb | Iterable[ServiceErrorPb],
    status_code: int = 1,
    status_message: str = "",
) -> Metadata:
    return grpc_status_of_errors(status_code, status_message, errors).trailing_metadata
