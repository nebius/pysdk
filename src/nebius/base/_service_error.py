from collections.abc import Iterable

from google.protobuf.any_pb2 import Any as AnyPb
from google.rpc.status_pb2 import Status as StatusPb  # type: ignore
from grpc import RpcError, Status, StatusCode
from grpc_status import rpc_status

from nebius.api.nebius.common.v1.error_pb2 import ServiceError as ServiceErrorPb


def pb2_from_status(
    status: StatusPb,  # type: ignore[unused-ignore]
    remove_from_details: bool = False,
) -> list[ServiceErrorPb]:
    ret = list[ServiceErrorPb]()
    rest = list[AnyPb]()
    for detail in status.details:  # type: ignore[unused-ignore]
        if detail.Is(ServiceErrorPb.DESCRIPTOR):  # type: ignore[unused-ignore]
            se = ServiceErrorPb()
            detail.Unpack(se)  # type: ignore[unused-ignore]
            ret.append(se)
        elif remove_from_details:
            rest.append(detail)  # type: ignore[unused-ignore]
    if remove_from_details:
        status.ClearField("details")  # type: ignore[unused-ignore]
        status.details.extend(rest)  # type: ignore[unused-ignore]
    return ret


def pb2_from_error(err: RpcError) -> list[ServiceErrorPb]:
    status = rpc_status.from_call(err)  # type: ignore[unused-ignore,arg-type]
    if status is None:
        return list[ServiceErrorPb]()
    return pb2_from_status(status)


def to_anypb(err: ServiceErrorPb) -> AnyPb:
    ret = AnyPb()
    ret.Pack(err)  # type: ignore[unused-ignore]
    return ret


def pbrpc_status_of_errors(  # type: ignore[unused-ignore]
    code: int,
    message: str,
    errors: ServiceErrorPb | Iterable[ServiceErrorPb],
) -> StatusPb:
    if isinstance(errors, ServiceErrorPb):
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
    errors: ServiceErrorPb | Iterable[ServiceErrorPb],
) -> Status:
    return rpc_status.to_status(pbrpc_status_of_errors(code, message, errors))


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
