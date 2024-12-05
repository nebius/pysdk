from typing import Iterable, Tuple, Union

from google.protobuf.any_pb2 import Any as AnyPb
from google.rpc.status_pb2 import Status as StatusPb  # type: ignore
from grpc import RpcError, Status
from grpc_status import rpc_status

from nebius.api.nebius.common.v1.error_pb2 import ServiceError as ServiceErrorPb


def pb2_from_status(status: StatusPb) -> list[ServiceErrorPb]:  # type: ignore[unused-ignore]
    ret = list[ServiceErrorPb]()
    for detail in status.details:  # type: ignore[unused-ignore]
        if detail.Is(ServiceErrorPb.DESCRIPTOR):  # type: ignore[unused-ignore]
            se = ServiceErrorPb()
            detail.Unpack(se)  # type: ignore[unused-ignore]
            ret.append(se)
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


Metadata = Tuple[
    Tuple[str, Union[str, bytes]],
    ...,
]


def trailing_metadata_of_errors(
    errors: ServiceErrorPb | Iterable[ServiceErrorPb],
) -> Metadata:
    return grpc_status_of_errors(1, "_", errors).trailing_metadata
