from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Project(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ProjectSpec
    status: ProjectStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ProjectSpec, _Mapping]] = ..., status: _Optional[_Union[ProjectStatus, _Mapping]] = ...) -> None: ...

class ProjectSpec(_message.Message):
    __slots__ = ["region"]
    REGION_FIELD_NUMBER: _ClassVar[int]
    region: str
    def __init__(self, region: _Optional[str] = ...) -> None: ...

class ProjectStatus(_message.Message):
    __slots__ = ["project_state"]
    class ProjectState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[ProjectStatus.ProjectState]
        CREATING: _ClassVar[ProjectStatus.ProjectState]
        ACTIVE: _ClassVar[ProjectStatus.ProjectState]
        PURGING: _ClassVar[ProjectStatus.ProjectState]
        CREATED: _ClassVar[ProjectStatus.ProjectState]
        ACTIVATING: _ClassVar[ProjectStatus.ProjectState]
        PARKING: _ClassVar[ProjectStatus.ProjectState]
        PARKED: _ClassVar[ProjectStatus.ProjectState]
    STATE_UNSPECIFIED: ProjectStatus.ProjectState
    CREATING: ProjectStatus.ProjectState
    ACTIVE: ProjectStatus.ProjectState
    PURGING: ProjectStatus.ProjectState
    CREATED: ProjectStatus.ProjectState
    ACTIVATING: ProjectStatus.ProjectState
    PARKING: ProjectStatus.ProjectState
    PARKED: ProjectStatus.ProjectState
    PROJECT_STATE_FIELD_NUMBER: _ClassVar[int]
    project_state: ProjectStatus.ProjectState
    def __init__(self, project_state: _Optional[_Union[ProjectStatus.ProjectState, str]] = ...) -> None: ...
