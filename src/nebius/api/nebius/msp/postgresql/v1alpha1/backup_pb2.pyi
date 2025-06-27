from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Backup(_message.Message):
    __slots__ = ["id", "source_cluster_id", "creation_start", "creation_finish", "source_cluster_name", "source_cluster_visible", "on_demand"]
    ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CLUSTER_ID_FIELD_NUMBER: _ClassVar[int]
    CREATION_START_FIELD_NUMBER: _ClassVar[int]
    CREATION_FINISH_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CLUSTER_NAME_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CLUSTER_VISIBLE_FIELD_NUMBER: _ClassVar[int]
    ON_DEMAND_FIELD_NUMBER: _ClassVar[int]
    id: str
    source_cluster_id: str
    creation_start: _timestamp_pb2.Timestamp
    creation_finish: _timestamp_pb2.Timestamp
    source_cluster_name: str
    source_cluster_visible: bool
    on_demand: bool
    def __init__(self, id: _Optional[str] = ..., source_cluster_id: _Optional[str] = ..., creation_start: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., creation_finish: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., source_cluster_name: _Optional[str] = ..., source_cluster_visible: bool = ..., on_demand: bool = ...) -> None: ...
