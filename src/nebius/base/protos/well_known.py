"""Adapters and mask helpers for well-known protobuf types."""

from datetime import datetime, timedelta, timezone
from typing import Any

from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp

from nebius.base.fieldmask import Mask

local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
"""Local timezone used when converting protobuf timestamps."""

# timestamp


def from_timestamp(t: Timestamp) -> datetime:
    """Convert a protobuf ``Timestamp`` to a timezone-aware ``datetime``.

    :param t: Protobuf timestamp.
    :returns: ``datetime`` localized to the system timezone.
    """
    return t.ToDatetime(local_timezone)


def ts_mask(_: Any) -> Mask:
    """Return a reset mask covering timestamp fields.

    :param _: Unused value placeholder.
    :returns: Mask covering ``seconds`` and ``nanos``.
    """
    return Mask(
        field_parts={
            "seconds": Mask(),
            "nanos": Mask(),
        }
    )


def to_timestamp(t: datetime | Timestamp) -> Timestamp:
    """Convert a ``datetime`` to a protobuf ``Timestamp``.

    :param t: ``datetime`` or already constructed ``Timestamp``.
    :returns: Protobuf timestamp.
    """
    if not isinstance(t, datetime):
        return t
    ret = Timestamp()
    ret.FromDatetime(t.astimezone(timezone.utc))
    return ret


# duration


def from_duration(d: Duration) -> timedelta:
    """Convert a protobuf ``Duration`` to ``timedelta``.

    :param d: Protobuf duration.
    :returns: ``timedelta`` value.
    """
    return d.ToTimedelta()


def to_duration(t: timedelta | Duration) -> Duration:
    """Convert a ``timedelta`` to a protobuf ``Duration``.

    :param t: ``timedelta`` or already constructed ``Duration``.
    :returns: Protobuf duration.
    """
    if not isinstance(t, timedelta):
        return t
    ret = Duration()
    ret.FromTimedelta(t)
    return ret


def duration_mask(_: Any) -> Mask:
    """Return a reset mask covering duration fields.

    :param _: Unused value placeholder.
    :returns: Mask covering ``seconds`` and ``nanos``.
    """
    return Mask(
        field_parts={
            "seconds": Mask(),
            "nanos": Mask(),
        }
    )


# status


def status_mask(_: Any) -> Mask:
    """Return a reset mask covering status fields.

    :param _: Unused value placeholder.
    :returns: Mask covering ``code``, ``message``, and ``details`` entries.
    """
    return Mask(
        field_parts={
            "code": Mask(),
            "message": Mask(),
            "details": Mask(
                any=Mask(
                    field_parts={
                        "type_url": Mask(),
                        "value": Mask(),
                    },
                )
            ),
        }
    )
