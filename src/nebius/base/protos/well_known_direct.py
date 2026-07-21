"""Provider-free Python views over authoritative direct WKT messages."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_TIMESTAMP_MIN_SECONDS = -62_135_596_800
_TIMESTAMP_MAX_SECONDS = 253_402_300_799


def _protobuf_full_name(value: object) -> str | None:
    direct_name = getattr(type(value), "__PROTO_FULL_NAME__", None)
    if isinstance(direct_name, str):
        return direct_name
    for owner in (value, type(value)):
        for attribute in ("DESCRIPTOR", "__PROTO_DESCRIPTOR__", "__PB2_DESCRIPTOR__"):
            descriptor = getattr(owner, attribute, None)
            full_name = getattr(descriptor, "full_name", None)
            if isinstance(full_name, str):
                return full_name
    return None


def _coerce_direct_message(value: object, message_type: type[Any], name: str) -> Any:
    if isinstance(value, message_type):
        return value
    if callable(getattr(value, "SerializeToString", None)):
        source_name = _protobuf_full_name(value)
        target_name = _protobuf_full_name(message_type())
        if source_name is None or source_name != target_name:
            raise TypeError(f"{name} field requires {name} or its Python view")
    try:
        return message_type(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{name} field requires {name} or its Python view") from error


def timestamp_to_datetime(value: Any) -> datetime:
    """Return a local-time datetime view without mutating the direct message."""
    if not _TIMESTAMP_MIN_SECONDS <= value.seconds <= _TIMESTAMP_MAX_SECONDS:
        raise ValueError(
            "timestamp seconds must be in the range for years 1 through 9999"
        )
    if not 0 <= value.nanos < 1_000_000_000:
        raise ValueError("timestamp nanos must be in the range [0, 999999999]")
    result = _EPOCH + timedelta(
        seconds=value.seconds,
        microseconds=value.nanos // 1000,
    )
    return result.astimezone(local_timezone)


def datetime_to_timestamp(value: object, factory: Callable[[], type[Any]]) -> Any:
    """Normalize a datetime/serializable timestamp into the localized direct type."""
    message_type = factory()
    if not isinstance(value, datetime):
        return _coerce_direct_message(value, message_type, "timestamp")
    delta = value.astimezone(timezone.utc) - _EPOCH
    seconds = delta.days * 86_400 + delta.seconds
    result = message_type()
    result.seconds = seconds
    result.nanos = value.microsecond * 1000
    return result


def duration_to_timedelta(value: Any) -> timedelta:
    """Return a timedelta view using protobuf's sub-microsecond truncation."""
    nanos = value.nanos
    microseconds = (abs(nanos) // 1000) * (-1 if nanos < 0 else 1)
    return timedelta(seconds=value.seconds, microseconds=microseconds)


def timedelta_to_duration(value: object, factory: Callable[[], type[Any]]) -> Any:
    """Normalize a timedelta/serializable duration into the localized direct type."""
    message_type = factory()
    if not isinstance(value, timedelta):
        return _coerce_direct_message(value, message_type, "duration")
    total_microseconds = (
        value.days * 86_400 + value.seconds
    ) * 1_000_000 + value.microseconds
    seconds = abs(total_microseconds) // 1_000_000
    if total_microseconds < 0:
        seconds = -seconds
    result = message_type()
    result.seconds = seconds
    result.nanos = (total_microseconds - seconds * 1_000_000) * 1000
    return result


def status_to_request_status(value: Any) -> Any:
    """Return an SDK status view retaining the direct value's registry."""
    from nebius.aio.request_status import request_status_from_rpc_status

    return request_status_from_rpc_status(value, registry=type(value).__REGISTRY__)


def request_status_to_status(value: object, factory: Callable[[], type[Any]]) -> Any:
    """Normalize an SDK/direct Status into the localized direct type."""
    from nebius.aio.request_status import RequestStatus

    message_type = factory()
    if isinstance(value, RequestStatus):
        return value.to_rpc_status(registry=message_type.__REGISTRY__)
    return _coerce_direct_message(value, message_type, "status")
