from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class NodeSetUnhealthyRequest(_message.Message):
    __slots__ = ["instance_id", "health_check_info", "dry_run"]
    class HealthCheckInfo(_message.Message):
        __slots__ = ["observed_at", "check_id", "description"]
        OBSERVED_AT_FIELD_NUMBER: _ClassVar[int]
        CHECK_ID_FIELD_NUMBER: _ClassVar[int]
        DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
        observed_at: _timestamp_pb2.Timestamp
        check_id: str
        description: str
        def __init__(self, observed_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., check_id: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    HEALTH_CHECK_INFO_FIELD_NUMBER: _ClassVar[int]
    DRY_RUN_FIELD_NUMBER: _ClassVar[int]
    instance_id: str
    health_check_info: NodeSetUnhealthyRequest.HealthCheckInfo
    dry_run: bool
    def __init__(self, instance_id: _Optional[str] = ..., health_check_info: _Optional[_Union[NodeSetUnhealthyRequest.HealthCheckInfo, _Mapping]] = ..., dry_run: bool = ...) -> None: ...

class NodeSetUnhealthyResponse(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
