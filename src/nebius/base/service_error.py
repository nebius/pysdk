from grpc import RpcError
from grpc_status import rpc_status

from nebius.api.nebius.common.v1.error_pb2 import ServiceError


def from_error(err: RpcError) -> list[ServiceError]:
    status = rpc_status.from_call(err)  # type: ignore[unused-ignore,arg-type]
    ret = list[ServiceError]()
    if status is None:
        return ret
    for detail in status.details:
        if detail.Is(ServiceError.DESCRIPTOR):
            se = ServiceError()
            detail.Unpack(se)
            ret.append(se)
    return ret
