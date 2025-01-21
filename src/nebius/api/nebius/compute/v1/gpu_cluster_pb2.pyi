from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GpuCluster(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: GpuClusterSpec
    status: GpuClusterStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[GpuClusterSpec, _Mapping]] = ..., status: _Optional[_Union[GpuClusterStatus, _Mapping]] = ...) -> None: ...

class GpuClusterSpec(_message.Message):
    __slots__ = ["infiniband_fabric"]
    INFINIBAND_FABRIC_FIELD_NUMBER: _ClassVar[int]
    infiniband_fabric: str
    def __init__(self, infiniband_fabric: _Optional[str] = ...) -> None: ...

class GpuClusterStatus(_message.Message):
    __slots__ = ["instances", "reconciling"]
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    instances: _containers.RepeatedScalarFieldContainer[str]
    reconciling: bool
    def __init__(self, instances: _Optional[_Iterable[str]] = ..., reconciling: bool = ...) -> None: ...
