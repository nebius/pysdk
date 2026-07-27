"""Registry-aware representations of final RPC status values."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from grpc import StatusCode

if TYPE_CHECKING:
    from nebius.base.protos.registry import Registry


class UnfinishedRequestStatus(Enum):
    """Sentinels used to represent a request that has not completed yet."""

    INITIALIZED = 1
    SENT = 2


def _status_code(value: int | StatusCode) -> StatusCode:
    if isinstance(value, StatusCode):
        return value
    for member in StatusCode:
        if member.value[0] == value:
            return member
    return StatusCode.UNKNOWN


def _status_registry(status: object, registry: Registry | None) -> Registry:
    if registry is not None:
        return registry
    owned = getattr(type(status), "__REGISTRY__", None)
    if owned is None:
        raise ValueError(
            "RPC status conversion requires an explicit or retained direct registry"
        )
    return cast("Registry", owned)


def _localized_status(status: object, registry: Registry) -> Any:
    status_type = registry.message_class("google.rpc.Status")
    if type(status) is status_type:
        return status_type(status)
    serializer = getattr(status, "SerializeToString", None)
    if not callable(serializer):
        raise TypeError("RPC status must be a serializable google.rpc.Status")
    descriptor = getattr(status, "DESCRIPTOR", None)
    full_name = getattr(descriptor, "full_name", None) or getattr(
        type(status), "__PROTO_FULL_NAME__", None
    )
    if full_name != "google.rpc.Status":
        raise TypeError("RPC status must be google.rpc.Status")
    return status_type.FromString(serializer())


@dataclass
class RequestStatus:
    """A normalized RPC status retaining its direct-message namespace."""

    code: StatusCode
    message: str | None
    details: list[Any]
    request_id: str
    trace_id: str
    registry: Registry | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )
    _raw_status: Any | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )
    _original_state: tuple[StatusCode, str | None, tuple[bytes, ...]] | None = field(
        default=None, init=False, repr=False, compare=False
    )

    def _state(self) -> tuple[StatusCode, str | None, tuple[bytes, ...]]:
        return (
            self.code,
            self.message,
            tuple(detail.SerializeToString() for detail in self.details),
        )

    def to_rpc_status(self, *, registry: Registry | None = None) -> Any:
        """Convert into the selected namespace's direct ``google.rpc.Status``."""
        selected = registry or self.registry
        if selected is None:
            raise ValueError(
                "RPC status conversion requires an explicit or retained direct registry"
            )
        if self._raw_status is not None and self._original_state is not None:
            localized = _localized_status(self._raw_status, selected)
            current_state = self._state()
            if current_state[0] != self._original_state[0]:
                localized.code = self.code.value[0]
            if current_state[1] != self._original_state[1]:
                localized.message = self.message or ""
            if current_state[2] == self._original_state[2]:
                return localized
            localized.details = self._localized_details(selected)
            return localized
        status_type = selected.message_class("google.rpc.Status")
        return status_type(
            code=self.code.value[0],
            message=self.message or "",
            details=self._localized_details(selected),
        )

    def _localized_details(self, selected: Registry) -> list[Any]:
        any_type = selected.message_class("google.protobuf.Any")
        details: list[Any] = []
        for detail in self.details:
            if type(detail) is any_type:
                details.append(detail)
                continue
            if getattr(type(detail), "__PROTO_FULL_NAME__", None) != (
                "google.protobuf.Any"
            ):
                raise TypeError("RPC status details must be google.protobuf.Any")
            details.append(any_type.FromString(detail.SerializeToString()))
        return details

    @classmethod
    def from_rpc_status(
        cls,
        status: object,
        request_id: str,
        trace_id: str,
        *,
        registry: Registry | None = None,
    ) -> RequestStatus:
        """Create a status using an explicit or direct-message-owned registry."""
        selected = _status_registry(status, registry)
        localized = _localized_status(status, selected)
        any_type = selected.message_class("google.protobuf.Any")
        result = cls(
            code=_status_code(localized.code),
            message=localized.message,
            details=[any_type(detail) for detail in localized.details],
            request_id=request_id,
            trace_id=trace_id,
            registry=selected,
            _raw_status=localized,
        )
        result._original_state = result._state()
        return result


def request_status_from_rpc_status(
    status: object, *, registry: Registry | None = None
) -> RequestStatus:
    """Convert a direct Status field into the SDK's extended status view."""
    from .service_error import RequestStatusExtended

    return RequestStatusExtended.from_rpc_status(
        status,
        request_id="",
        trace_id="",
        registry=registry,
    )


def request_status_to_rpc_status(
    status: RequestStatus, *, registry: Registry | None = None
) -> Any:
    """Convert an SDK status into a namespace-local direct Status."""
    return status.to_rpc_status(registry=registry)


def rpc_status_from_call(call: Any, *, registry: Registry | None) -> Any | None:
    """Decode and validate rich gRPC status metadata into a direct Status."""
    metadata = call.trailing_metadata()
    if metadata is None:
        return None
    for key, value in metadata:
        if key != "grpc-status-details-bin":
            continue
        if registry is None:
            raise ValueError("rich gRPC status decoding requires a direct registry")
        status: Any = registry.message_class("google.rpc.Status").FromString(value)
        if call.code().value[0] != status.code:
            raise ValueError("Status proto code does not match the gRPC status code")
        if call.details() != status.message:
            raise ValueError("Status proto message does not match gRPC status details")
        return status
    return None
