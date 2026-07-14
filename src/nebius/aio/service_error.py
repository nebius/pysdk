"""Helpers for converting service-level protobuf errors into SDK types.

This module builds on :mod:`request_status` to represent detailed service
errors (``ServiceError`` PBs) and to decide retriability based on service
semantics and gRPC status codes.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from io import StringIO
from typing import TYPE_CHECKING, Any, cast

from grpc import StatusCode

from nebius.aio.request import RequestError as BaseError
from nebius.aio.request_status import RequestStatus

if TYPE_CHECKING:
    from nebius.base.protos.direct import Message
    from nebius.base.protos.registry import Registry

_SERVICE_ERROR_NAMES = frozenset(
    {
        "nebius.common.v1.ServiceError",
        "nebius.common.error.v1alpha1.ServiceError",
    }
)


class RequestError(BaseError):
    """Exception raised for requests that failed with service-level errors.

    The exception carries a :class:`RequestStatusExtended` instance in its
    ``status`` attribute providing structured details about the failure.
    """

    status: "RequestStatusExtended"

    def __init__(self, status: "RequestStatusExtended") -> None:
        self.status = status

        super().__init__(f"Request error {str(status)}")


def to_str(err: Any) -> str:
    """Render a :class:`ServiceError` into a concise human readable string.

    The function inspects typed details attached to the service error and
    produces a one-line summary intended for logs and exception messages.
    """
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
            case "operation_conflict":
                ret.write(" operation conflict: resource: ")
                ret.write(err.details.value.resource_id)
                ret.write(", conflicting operation ID: ")
                ret.write(err.details.value.conflicting_operation_id)
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
            case _:
                # must not be used, but is added for forward compatibility with new
                # error types, while the error type is not published in the API, but
                # needs some representation.
                ret.write(" ")
                ret.write(err.details.field)
                ret.write(": ")
                ret.write(repr(err.details.value))
    return ret.getvalue()


code_map = {i.value[0]: i for i in StatusCode}  # type: ignore[index,unused-ignore]


def int_to_status_code(i: int | StatusCode) -> StatusCode:
    """Convert an integer or StatusCode into a :class:`StatusCode` instance.

    Useful when reading numeric status codes from protobuf messages.
    """
    if isinstance(i, StatusCode):
        return i
    if i in code_map:
        return code_map[i]
    return StatusCode.UNKNOWN


DefaultRetriableCodes = [
    StatusCode.RESOURCE_EXHAUSTED,
    StatusCode.UNAVAILABLE,
]

_HTTP_STATUS_PATTERNS = [
    re.compile(
        r"\bunexpected\s+http\s+status(?:\s+code)?"
        r"(?:\s+received\s+from\s+server)?\s*[:=]?\s*(?P<code>\d{3})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breceived\s+http2?\s+header\s+with\s+status\s*[:=]?\s*" r"(?P<code>\d{3})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhttp(?:/2|2)?\s+status(?:\s+code)?\s*[:=]?\s*" r"(?P<code>\d{3})",
        re.IGNORECASE,
    ),
]


def _is_unknown_code(code: object) -> bool:
    """Return True when a gRPC status code value represents UNKNOWN."""
    if code == StatusCode.UNKNOWN:
        return True
    if code == StatusCode.UNKNOWN.value[0]:
        return True
    if (
        isinstance(code, tuple)
        and len(code) > 0
        and code[0] == StatusCode.UNKNOWN.value[0]
    ):
        return True
    return getattr(code, "name", None) == "UNKNOWN"


def _has_unexpected_http_52x_status(message: str | None) -> bool:
    """Detect proxy-originated HTTP 52x statuses in Python gRPC messages."""
    if not message:
        return False
    for pattern in _HTTP_STATUS_PATTERNS:
        for match in pattern.finditer(message):
            code = int(match.group("code"))
            if 520 <= code < 530:
                return True
    return False


def _call_error_method(err: BaseException, name: str) -> object | None:
    value = getattr(err, name, None)
    if value is None:
        return None
    if not callable(value):
        return cast(object, value)
    method = cast(Callable[[], object], value)
    try:
        return method()
    except Exception:
        return None


def _grpc_error_has_unknown_http_52x_status(err: BaseException) -> bool:
    code = _call_error_method(err, "code")
    if not _is_unknown_code(code):
        return False
    for message in (
        _call_error_method(err, "details"),
        _call_error_method(err, "debug_error_string"),
        str(err),
    ):
        if _has_unexpected_http_52x_status(None if message is None else str(message)):
            return True
    return False


def _iter_error_chain(err: BaseException) -> Iterable[BaseException]:
    seen: set[int] = set()
    cur: BaseException | None = err
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        yield cur
        if cur.__cause__ is not None:
            cur = cur.__cause__
            continue
        if cur.__context__ is not None and not cur.__suppress_context__:
            cur = cur.__context__
            continue
        cur = None


@dataclass
class RequestStatusExtended(RequestStatus):
    """Extended request status that includes parsed service errors.

    This supplements :class:`RequestStatus` with a list of domain-specific
    :class:`ServiceError` messages extracted from the status details.

    :ivar code: gRPC status code
    :ivar message: human readable message (may be ``None``)
    :ivar details: list of ``google.protobuf.Any`` detail messages
    :ivar service_errors: list of parsed :class:`ServiceError` messages
    :ivar request_id: request identifier extracted from metadata
    :ivar trace_id: trace identifier extracted from metadata
    """

    code: StatusCode
    message: str | None
    details: list[Any]
    service_errors: list[Any]
    request_id: str
    trace_id: str
    _original_extended_state: (
        tuple[tuple[StatusCode, str | None, tuple[bytes, ...]], tuple[bytes, ...]]
        | None
    ) = field(default=None, init=False, repr=False, compare=False)

    def _extended_state(
        self,
    ) -> tuple[tuple[StatusCode, str | None, tuple[bytes, ...]], tuple[bytes, ...]]:
        return (
            self._state(),
            tuple(error.SerializeToString() for error in self.service_errors),
        )

    def __str__(self) -> str:
        """Render a compact human-readable representation of the status.

        This is used when building exception messages for :class:`RequestError`.
        """
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

    def to_rpc_status(self, *, registry: Registry | None = None) -> Any:
        """Convert this extended status back into a protobuf Status.

        Service errors are packed into Any messages and included in the
        returned Status details.
        """
        selected = registry or self.registry
        if selected is None:
            raise ValueError(
                "RPC status conversion requires an explicit or retained direct registry"
            )
        current_state = self._extended_state()
        if self._raw_status is not None and self._original_extended_state is not None:
            from nebius.aio.request_status import _localized_status

            ret = _localized_status(self._raw_status, selected)
            original_base = self._original_extended_state[0]
            if current_state[0][0] != original_base[0]:
                ret.code = self.code.value[0]
            if current_state[0][1] != original_base[1]:
                ret.message = self.message or ""
            if current_state == self._original_extended_state:
                return ret
        else:
            ret = super().to_rpc_status(registry=selected)
        localized_errors: list[Message] = []
        for error in self.service_errors:
            full_name = getattr(type(error), "__PROTO_FULL_NAME__", None)
            if full_name not in _SERVICE_ERROR_NAMES:
                raise TypeError("service error has an unexpected protobuf type")
            error_type = selected.message_class(full_name)
            if type(error) is error_type:
                localized_errors.append(error)
                continue
            localized_errors.append(error_type._from_string(error.SerializeToString()))
        packed_errors = [selected.pack_any(error) for error in localized_errors]
        if self._raw_status is not None:
            ret.details = [*self._localized_details(selected), *packed_errors]
        else:
            ret.details.extend(packed_errors)
        return ret

    @classmethod
    def from_rpc_status(
        cls,
        status: object,
        request_id: str,
        trace_id: str,
        *,
        registry: Registry | None = None,
    ) -> "RequestStatusExtended":
        """Construct an extended status by extracting ServiceError protos.

        This function uses internal helper :func:`pb2_from_status` to remove
        service error protos from the details and returns them as
        :class:`ServiceError` wrappers.
        """
        base = RequestStatus.from_rpc_status(
            status,
            request_id=request_id,
            trace_id=trace_id,
            registry=registry,
        )
        if base.registry is None:
            raise ValueError("direct RPC status conversion lost its registry")
        errors: list[Any] = []
        rest: list[Any] = []
        for detail in base.details:
            try:
                full_name = base.registry.type_name(detail.type_url)
            except ValueError:
                rest.append(detail)
                continue
            if full_name not in _SERVICE_ERROR_NAMES:
                rest.append(detail)
                continue
            try:
                errors.append(base.registry.unpack_any(detail))
            except LookupError:
                rest.append(detail)
        result = cls(
            code=base.code,
            message=base.message,
            details=rest,
            service_errors=errors,
            request_id=request_id,
            trace_id=trace_id,
            registry=base.registry,
            _raw_status=base._raw_status,
        )
        result._original_extended_state = result._extended_state()
        return result

    def is_retriable(self, deadline_retriable: bool = False) -> bool:
        """Return True when the status is considered retriable.

        Retriability is determined by inspecting service-level retry hints and
        a set of default gRPC status codes. When ``deadline_retriable`` is
        True the DEADLINE_EXCEEDED code is considered retriable.
        """
        # Check service errors
        for service_error in self.service_errors:
            if hasattr(service_error, "retry_type"):
                retry_type = service_error.retry_type
                retry_name = getattr(retry_type, "name", None)
                if retry_name == "CALL":
                    return True
                if retry_name in {"NOTHING", "UNIT_OF_WORK"}:
                    return False

        # Check gRPC error codes
        if self.code in DefaultRetriableCodes:
            return True

        if deadline_retriable and self.code == StatusCode.DEADLINE_EXCEEDED:
            return True

        if _is_unknown_code(self.code) and _has_unexpected_http_52x_status(
            self.message
        ):
            return True

        return False


def is_retriable_error(err: Exception, deadline_retriable: bool = False) -> bool:
    """Decide whether an exception should be retried.

    The function recognizes :class:`RequestError` (service-level errors) and
    also checks for common network/transport error conditions.
    """
    for chained_err in _iter_error_chain(err):
        if isinstance(chained_err, RequestError):
            return chained_err.status.is_retriable(deadline_retriable)

        if _grpc_error_has_unknown_http_52x_status(chained_err):
            return True

        # Network and transport error handling
        if isinstance(chained_err, Exception) and (
            is_network_error(chained_err)
            or is_transport_error(chained_err)
            or is_dns_error(chained_err)
        ):
            return True

    return False


def is_network_error(err: Exception) -> bool:
    """Return True for network errors that look like timeouts."""
    if isinstance(err, OSError) and "timed out" in str(err):
        return True
    return False


def is_transport_error(err: Exception) -> bool:
    """Return True for transport-level errors such as connection reset.

    This is a heuristic based on the textual content of the exception.
    """
    if isinstance(err, OSError) and (
        "connection refused" in str(err) or "connection reset" in str(err)
    ):
        return True
    return False


def is_dns_error(err: Exception) -> bool:
    """Return True when an exception indicates a DNS resolution problem."""
    return "name resolution" in str(err)
