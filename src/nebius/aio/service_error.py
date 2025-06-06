from dataclasses import dataclass
from io import StringIO

from google.protobuf.any_pb2 import Any as AnyPb
from google.rpc.status_pb2 import Status as StatusPb  # type: ignore
from grpc import StatusCode

from nebius.aio.request import RequestError as BaseError
from nebius.aio.request_status import RequestStatus
from nebius.api.nebius.common.v1 import ServiceError
from nebius.base._service_error import pb2_from_status  # type: ignore[unused-ignore]


def to_anypb(err: ServiceError) -> AnyPb:
    ret = AnyPb()
    ret.Pack(err.__pb2_message__)  # type: ignore[unused-ignore]
    return ret


class RequestError(BaseError):
    status: "RequestStatusExtended"

    def __init__(self, status: "RequestStatusExtended") -> None:
        self.status = status

        super().__init__(f"Request error {str(status)}")


def to_str(err: ServiceError) -> str:
    ret = StringIO("Error ")
    ret.write(err.code)
    ret.write(" in service ")
    ret.write(err.service)
    if err.details is not None:
        match err.details.field:
            case "bad_request":
                ret.write(" bad request, violations:")
                for violation in err.details.value.violations:
                    ret.write(" ")
                    ret.write(violation.field)
                    ret.write(" - ")
                    ret.write(violation.message)
                    ret.write(";")
            case "bad_resource_state":
                ret.write(" bad resource ")
                ret.write(err.details.value.resource_id)
                ret.write(" state: ")
                ret.write(err.details.value.message)
            case "resource_not_found":
                ret.write(" resource ")
                ret.write(err.details.value.resource_id)
                ret.write(" not found")
            case "resource_already_exists":
                ret.write(" resource ")
                ret.write(err.details.value.resource_id)
                ret.write(" already exists")
            case "out_of_range":
                ret.write(" out of range ")
                ret.write(err.details.value.limit)
                ret.write(", requested ")
                ret.write(err.details.value.requested)
            case "permission_denied":
                ret.write(" permission denied for resource ")
                ret.write(err.details.value.resource_id)
            case "resource_conflict":
                ret.write(" resource conflict for ")
                ret.write(err.details.value.resource_id)
                ret.write(": ")
                ret.write(err.details.value.message)
            case "operation_aborted":
                ret.write(" operation ")
                ret.write(err.details.value.operation_id)
                ret.write(" over resource ")
                ret.write(err.details.value.resource_id)
                ret.write(" aborted by newer operation ")
                ret.write(err.details.value.aborted_by_operation_id)
            case "too_many_requests":
                ret.write(" too many requests: ")
                ret.write(err.details.value.violation)
            case "quota_failure":
                ret.write(" quota failure, violations: ")
                for quota_violation in err.details.value.violations:
                    ret.write(" ")
                    ret.write(quota_violation.quota)
                    ret.write(" ")
                    ret.write(quota_violation.requested)
                    ret.write(" of ")
                    ret.write(quota_violation.limit)
                    ret.write(": ")
                    ret.write(quota_violation.message)
                    ret.write(";")
            case "not_enough_resources":
                ret.write(" not enough resources: ")
                for ner_violation in err.details.value.violations:
                    ret.write(" ")
                    ret.write(ner_violation.resource_type)
                    ret.write(" requested ")
                    ret.write(ner_violation.requested)
                    ret.write(": ")
                    ret.write(ner_violation.message)
                    ret.write(";")
            case "internal_error":
                ret.write(" internal service error: request ID: ")
                ret.write(err.details.value.request_id)
                ret.write(" trace ID: ")
                ret.write(err.details.value.trace_id)
    return ret.getvalue()


code_map = {i.value[0]: i for i in StatusCode}  # type: ignore[index]


def int_to_status_code(i: int | StatusCode) -> StatusCode:
    if isinstance(i, StatusCode):
        return i
    if i in code_map:
        return code_map[i]
    return StatusCode.UNKNOWN


DefaultRetriableCodes = [
    StatusCode.RESOURCE_EXHAUSTED,
    StatusCode.UNAVAILABLE,
]


@dataclass
class RequestStatusExtended(RequestStatus):
    code: StatusCode
    message: str | None
    details: list[AnyPb]
    service_errors: list[ServiceError]
    request_id: str
    trace_id: str

    def __str__(self) -> str:
        ret = StringIO()
        ret.write(f"{StatusCode(self.code).name}")
        if self.message is not None:
            ret.write(": ")
            ret.write(self.message)
        if self.request_id != "":
            ret.write("; request_id: ")
            ret.write(self.request_id)
        if self.trace_id != "":
            ret.write("; trace_id: ")
            ret.write(self.trace_id)
        if len(self.service_errors) > 0:
            ret.write("; Caused by error")
            if len(self.service_errors) > 1:
                ret.write("s")
            ret.write(":")
            inc = 0
            for err in self.service_errors:
                inc += 1
                ret.write(f" {inc}. ")
                ret.write(to_str(err))
        if len(self.details) > 0:
            ret.write(" (additional details not shown)")
        return ret.getvalue()

    def to_rpc_status(self) -> StatusPb:  # type: ignore[unused-ignore]
        ret = StatusPb()  # type: ignore[unused-ignore]
        ret.code = self.code
        ret.message = self.message
        ret.details.extend(self.details)  # type: ignore[unused-ignore]
        ret.details.extend([to_anypb(err) for err in self.service_errors])  # type: ignore[unused-ignore]
        return ret  # type: ignore[unused-ignore]

    @classmethod
    def from_rpc_status(
        cls,
        status: StatusPb,  # type: ignore[unused-ignore]
        request_id: str,
        trace_id: str,
    ) -> "RequestStatusExtended":
        errors = pb2_from_status(status, remove_from_details=True)  # type: ignore[unused-ignore]
        return cls(
            code=int_to_status_code(status.code),  # type: ignore[unused-ignore]
            message=status.message,  # type: ignore[unused-ignore]
            details=[d for d in status.details],  # type: ignore[unused-ignore]
            service_errors=[ServiceError(err) for err in errors],
            request_id=request_id,
            trace_id=trace_id,
        )

    def is_retriable(self, deadline_retriable: bool = False) -> bool:
        # Check service errors
        for service_error in self.service_errors:
            if hasattr(service_error, "retry_type"):
                retry_type = service_error.retry_type
                if retry_type == ServiceError.RetryType.CALL:
                    return True
                if retry_type in [
                    ServiceError.RetryType.NOTHING,
                    ServiceError.RetryType.UNIT_OF_WORK,
                ]:
                    return False

        # Check gRPC error codes
        if self.code in DefaultRetriableCodes:
            return True

        if deadline_retriable and self.code == StatusCode.DEADLINE_EXCEEDED:
            return True

        return False


def is_retriable_error(err: Exception, deadline_retriable: bool = False) -> bool:
    if isinstance(err, RequestError):
        return err.status.is_retriable(deadline_retriable)

    # Network and transport error handling
    if is_network_error(err) or is_transport_error(err) or is_dns_error(err):
        return True

    return False


def is_network_error(err: Exception) -> bool:
    if isinstance(err, OSError) and "timed out" in str(err):
        return True
    return False


def is_transport_error(err: Exception) -> bool:
    if isinstance(err, OSError) and (
        "connection refused" in str(err) or "connection reset" in str(err)
    ):
        return True
    return False


def is_dns_error(err: Exception) -> bool:
    return "name resolution" in str(err)
