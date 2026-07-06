from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DiskSnapshot(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: DiskSnapshotSpec
    status: DiskSnapshotStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[DiskSnapshotSpec, _Mapping]] = ..., status: _Optional[_Union[DiskSnapshotStatus, _Mapping]] = ...) -> None: ...

class DiskSnapshotSpec(_message.Message):
    __slots__ = ["source_disk_id", "description"]
    SOURCE_DISK_ID_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    source_disk_id: str
    description: str
    def __init__(self, source_disk_id: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class DiskSnapshotStatus(_message.Message):
    __slots__ = ["state", "content_size_bytes", "storage_size_bytes", "lock_state", "source_cpu_architecture"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[DiskSnapshotStatus.State]
        CREATING: _ClassVar[DiskSnapshotStatus.State]
        READY: _ClassVar[DiskSnapshotStatus.State]
        DELETING: _ClassVar[DiskSnapshotStatus.State]
        ERROR: _ClassVar[DiskSnapshotStatus.State]
    UNSPECIFIED: DiskSnapshotStatus.State
    CREATING: DiskSnapshotStatus.State
    READY: DiskSnapshotStatus.State
    DELETING: DiskSnapshotStatus.State
    ERROR: DiskSnapshotStatus.State
    class CPUArchitecture(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNDEFINED: _ClassVar[DiskSnapshotStatus.CPUArchitecture]
        AMD64: _ClassVar[DiskSnapshotStatus.CPUArchitecture]
        ARM64: _ClassVar[DiskSnapshotStatus.CPUArchitecture]
    UNDEFINED: DiskSnapshotStatus.CPUArchitecture
    AMD64: DiskSnapshotStatus.CPUArchitecture
    ARM64: DiskSnapshotStatus.CPUArchitecture
    class LockState(_message.Message):
        __slots__ = ["disks"]
        DISKS_FIELD_NUMBER: _ClassVar[int]
        disks: _containers.RepeatedScalarFieldContainer[str]
        def __init__(self, disks: _Optional[_Iterable[str]] = ...) -> None: ...
    STATE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    STORAGE_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    LOCK_STATE_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CPU_ARCHITECTURE_FIELD_NUMBER: _ClassVar[int]
    state: DiskSnapshotStatus.State
    content_size_bytes: int
    storage_size_bytes: int
    lock_state: DiskSnapshotStatus.LockState
    source_cpu_architecture: DiskSnapshotStatus.CPUArchitecture
    def __init__(self, state: _Optional[_Union[DiskSnapshotStatus.State, str]] = ..., content_size_bytes: _Optional[int] = ..., storage_size_bytes: _Optional[int] = ..., lock_state: _Optional[_Union[DiskSnapshotStatus.LockState, _Mapping]] = ..., source_cpu_architecture: _Optional[_Union[DiskSnapshotStatus.CPUArchitecture, str]] = ...) -> None: ...
