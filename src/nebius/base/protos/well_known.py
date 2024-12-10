from datetime import datetime, timedelta, timezone

from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp

local_timezone = datetime.now(timezone.utc).astimezone().tzinfo


def from_timestamp(t: Timestamp) -> datetime:
    return t.ToDatetime(local_timezone)


def to_timestamp(t: datetime | Timestamp) -> Timestamp:
    if not isinstance(t, datetime):
        return t
    ret = Timestamp()
    ret.FromDatetime(t.astimezone(timezone.utc))
    return ret


def from_duration(d: Duration) -> timedelta:
    return d.ToTimedelta()


def to_duration(t: timedelta | Duration) -> Duration:
    if not isinstance(t, timedelta):
        return t
    ret = Duration()
    ret.FromTimedelta(t)
    return ret
