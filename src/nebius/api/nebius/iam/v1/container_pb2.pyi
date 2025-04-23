from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.iam.v1 import state_pb2 as _state_pb2
from nebius.api.nebius.iam.v1 import suspension_state_pb2 as _suspension_state_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Container(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ContainerSpec
    status: ContainerStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ContainerSpec, _Mapping]] = ..., status: _Optional[_Union[ContainerStatus, _Mapping]] = ...) -> None: ...

class ContainerSpec(_message.Message):
    __slots__ = ["region"]
    REGION_FIELD_NUMBER: _ClassVar[int]
    region: str
    def __init__(self, region: _Optional[str] = ...) -> None: ...

class ContainerStatus(_message.Message):
    __slots__ = ["suspension_state", "container_state", "region"]
    SUSPENSION_STATE_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_STATE_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    suspension_state: _suspension_state_pb2.SuspensionState
    container_state: _state_pb2.State
    region: str
    def __init__(self, suspension_state: _Optional[_Union[_suspension_state_pb2.SuspensionState, str]] = ..., container_state: _Optional[_Union[_state_pb2.State, str]] = ..., region: _Optional[str] = ...) -> None: ...
