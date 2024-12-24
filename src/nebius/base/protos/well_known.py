from datetime import datetime, timedelta, timezone
from typing import Any

from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp

from nebius.base.fieldmask import Mask

local_timezone = datetime.now(timezone.utc).astimezone().tzinfo

# timestamp


def from_timestamp(t: Timestamp) -> datetime:
    return t.ToDatetime(local_timezone)


def ts_mask(_: Any) -> Mask:
    return Mask(
        field_parts={
            "seconds": Mask(),
            "nanos": Mask(),
        }
    )


def to_timestamp(t: datetime | Timestamp) -> Timestamp:
    if not isinstance(t, datetime):
        return t
    ret = Timestamp()
    ret.FromDatetime(t.astimezone(timezone.utc))
    return ret


# duration


def from_duration(d: Duration) -> timedelta:
    return d.ToTimedelta()


def to_duration(t: timedelta | Duration) -> Duration:
    if not isinstance(t, timedelta):
        return t
    ret = Duration()
    ret.FromTimedelta(t)
    return ret


def duration_mask(_: Any) -> Mask:
    return Mask(
        field_parts={
            "seconds": Mask(),
            "nanos": Mask(),
        }
    )


# status


def status_mask(_: Any) -> Mask:
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
