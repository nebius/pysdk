from collections.abc import Iterable
from typing import Any

from google.protobuf.any_pb2 import Any as AnyPb
from google.rpc.status_pb2 import Status as StatusPb  # type: ignore
from grpc import RpcError, Status, StatusCode
from grpc_status import rpc_status


def pb2_from_status(
    status: StatusPb,  # type: ignore[unused-ignore]
    remove_from_details: bool = False,
) -> list[bytes]:
    ret: list[bytes] = []
    rest = list[AnyPb]()
    for detail in status.details:  # type: ignore[unused-ignore]
        if detail.type_url.rsplit("/", 1)[-1] == "nebius.common.v1.ServiceError":
            ret.append(bytes(detail.value))
        elif remove_from_details:
            rest.append(detail)  # type: ignore[unused-ignore]
    if remove_from_details:
        status.ClearField("details")  # type: ignore[unused-ignore]
        status.details.extend(rest)  # type: ignore[unused-ignore]
    return ret


def pb2_from_error(err: RpcError) -> list[bytes]:
    status = rpc_status.from_call(err)  # type: ignore[unused-ignore,arg-type]
    if status is None:
        return []
    return pb2_from_status(status)


def to_anypb(err: Any) -> AnyPb:
    descriptor = (
        err.get_descriptor() if hasattr(err, "get_descriptor") else err.DESCRIPTOR
    )
    return AnyPb(
        type_url=f"type.googleapis.com/{descriptor.full_name}",
        value=err.SerializeToString(),
    )


def pbrpc_status_of_errors(  # type: ignore[unused-ignore]
    code: int,
    message: str,
    errors: Any | Iterable[Any],
) -> StatusPb:
    if hasattr(errors, "SerializeToString"):
        errors = [errors]
    pbs = [to_anypb(err) for err in errors]
    ret = StatusPb()  # type: ignore[unused-ignore]
    if isinstance(code, StatusCode):
        ret.code = code[0]  # type: ignore
    elif isinstance(code, tuple) and isinstance(code[0], int):
        ret.code = code[0]
    else:
        ret.code = code
    ret.message = message
    ret.details.extend(pbs)  # type: ignore[unused-ignore]
    return ret  # type: ignore[unused-ignore]


def grpc_status_of_errors(
    code: int,
    message: str,
    errors: Any | Iterable[Any],
) -> Status:
    return rpc_status.to_status(pbrpc_status_of_errors(code, message, errors))


Metadata = tuple[
    tuple[str, str | bytes],
    ...,
]


def trailing_metadata_of_errors(
    errors: Any | Iterable[Any],
    status_code: int = 1,
    status_message: str = "",
) -> Metadata:
    return grpc_status_of_errors(status_code, status_message, errors).trailing_metadata
