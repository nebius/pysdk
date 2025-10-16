"""Types for representing the request status returned by RPCs.

This module exposes a small set of helpers used by the request logic to
represent final request statuses and to convert to/from gRPC's
``google.rpc.Status`` representation. The lightweight :class:`RequestStatus`
is used where service-specific details are not required. When the SDK is
aware of service-level errors the richer :class:`RequestStatusExtended` from
``service_error`` is used instead.
"""

from dataclasses import dataclass
from enum import Enum

from google.protobuf.any_pb2 import Any as AnyPb
from google.rpc.status_pb2 import Status as StatusPb  # type: ignore
from grpc import StatusCode


class UnfinishedRequestStatus(Enum):
    """Sentinels used to represent a request that hasn't completed yet."""

    INITIALIZED = 1
    """Request has been initialized but not yet sent.
    """
    SENT = 2
    """Request has been sent but not yet completed.
    """


@dataclass
class RequestStatus:
    """A normalized representation of an RPC status.

    :ivar code: gRPC status code
    :ivar message: human readable message (may be ``None``)
    :ivar details: list of ``google.protobuf.Any`` detail messages
    :ivar request_id: request identifier extracted from metadata
    :ivar trace_id: trace identifier extracted from metadata
    """

    code: StatusCode
    message: str | None
    details: list[AnyPb]
    request_id: str
    trace_id: str

    def to_rpc_status(self) -> StatusPb:  # type: ignore[unused-ignore]
        """Convert this object into a :class:`google.rpc.status_pb2.Status`.

        This is primarily used when the SDK needs to interoperate with
        gRPC-based status helpers.
        """
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
        """Create a :class:`RequestStatus` from a gRPC Status proto.

        :param status: the protobuf status message
        :param request_id: request id extracted separately from metadata
        :param trace_id: trace id extracted separately from metadata
        :returns: a populated :class:`RequestStatus` instance
        """
        return cls(
            code=status.code,  # type: ignore[unused-ignore]
            message=status.message,  # type: ignore[unused-ignore]
            details=[d for d in status.details],  # type: ignore[unused-ignore]
            request_id=request_id,
            trace_id=trace_id,
        )


def request_status_from_rpc_status(status: StatusPb) -> RequestStatus:  # type: ignore[unused-ignore]
    """Convert a protobuf Status to the SDK's :class:`RequestStatus`.

    When service-level error details are available the SDK uses the richer
    :class:`RequestStatusExtended` defined in :mod:`service_error`.
    """
    from .service_error import RequestStatusExtended

    return RequestStatusExtended.from_rpc_status(status, request_id="", trace_id="")  # type: ignore[unused-ignore]


def request_status_to_rpc_status(status: RequestStatus) -> StatusPb:  # type: ignore[unused-ignore]
    """Convert an SDK :class:`RequestStatus` back into a protobuf Status."""
    return status.to_rpc_status()  # type: ignore[unused-ignore]
