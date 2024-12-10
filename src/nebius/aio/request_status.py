from dataclasses import dataclass
from enum import Enum

from google.protobuf.any_pb2 import Any as AnyPb
from google.rpc.status_pb2 import Status as StatusPb  # type: ignore
from grpc import StatusCode


class UnfinishedRequestStatus(Enum):
    INITIALIZED = 1
    SENT = 2


@dataclass
class RequestStatus:
    code: StatusCode
    message: str | None
    details: list[AnyPb]
    request_id: str
    trace_id: str

    def to_rpc_status(self) -> StatusPb:  # type: ignore[unused-ignore]
        ret = StatusPb()  # type: ignore[unused-ignore]
        ret.code = self.code
        ret.message = self.message
        ret.details.extend(self.details)  # type: ignore[unused-ignore]
        return ret  # type: ignore[unused-ignore]

    @classmethod
    def from_rpc_status(
        cls,
        status: StatusPb,  # type: ignore[unused-ignore]
        request_id: str,
        trace_id: str,
    ) -> "RequestStatus":
        return cls(
            code=status.code,  # type: ignore[unused-ignore]
            message=status.message,  # type: ignore[unused-ignore]
            details=[d for d in status.details],  # type: ignore[unused-ignore]
            request_id=request_id,
            trace_id=trace_id,
        )


def request_status_from_rpc_status(status: StatusPb) -> RequestStatus:  # type: ignore[unused-ignore]
    from .service_error import RequestStatusExtended

    return RequestStatusExtended.from_rpc_status(status, request_id="", trace_id="")  # type: ignore[unused-ignore]


def request_status_to_rpc_status(status: RequestStatus) -> StatusPb:  # type: ignore[unused-ignore]
    return status.to_rpc_status()  # type: ignore[unused-ignore]
