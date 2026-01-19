from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TargetGroup(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: TargetGroupSpec
    status: TargetGroupStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[TargetGroupSpec, _Mapping]] = ..., status: _Optional[_Union[TargetGroupStatus, _Mapping]] = ...) -> None: ...

class TargetGroupSpec(_message.Message):
    __slots__ = ["targets"]
    TARGETS_FIELD_NUMBER: _ClassVar[int]
    targets: _containers.RepeatedCompositeFieldContainer[Target]
    def __init__(self, targets: _Optional[_Iterable[_Union[Target, _Mapping]]] = ...) -> None: ...

class Target(_message.Message):
    __slots__ = ["compute_instance"]
    COMPUTE_INSTANCE_FIELD_NUMBER: _ClassVar[int]
    compute_instance: ComputeInstance
    def __init__(self, compute_instance: _Optional[_Union[ComputeInstance, _Mapping]] = ...) -> None: ...

class ComputeInstance(_message.Message):
    __slots__ = ["id", "network_interface_name"]
    ID_FIELD_NUMBER: _ClassVar[int]
    NETWORK_INTERFACE_NAME_FIELD_NUMBER: _ClassVar[int]
    id: str
    network_interface_name: str
    def __init__(self, id: _Optional[str] = ..., network_interface_name: _Optional[str] = ...) -> None: ...

class TargetGroupStatus(_message.Message):
    __slots__ = ["load_balancer_ids", "target_statuses"]
    LOAD_BALANCER_IDS_FIELD_NUMBER: _ClassVar[int]
    TARGET_STATUSES_FIELD_NUMBER: _ClassVar[int]
    load_balancer_ids: _containers.RepeatedScalarFieldContainer[str]
    target_statuses: _containers.RepeatedCompositeFieldContainer[TargetStatus]
    def __init__(self, load_balancer_ids: _Optional[_Iterable[str]] = ..., target_statuses: _Optional[_Iterable[_Union[TargetStatus, _Mapping]]] = ...) -> None: ...

class TargetStatus(_message.Message):
    __slots__ = ["compute_instance_id", "target_state"]
    class TargetState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        TARGET_STATE_UNSPECIFIED: _ClassVar[TargetStatus.TargetState]
        READY: _ClassVar[TargetStatus.TargetState]
        DISABLED: _ClassVar[TargetStatus.TargetState]
        DELETED: _ClassVar[TargetStatus.TargetState]
    TARGET_STATE_UNSPECIFIED: TargetStatus.TargetState
    READY: TargetStatus.TargetState
    DISABLED: TargetStatus.TargetState
    DELETED: TargetStatus.TargetState
    COMPUTE_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_STATE_FIELD_NUMBER: _ClassVar[int]
    compute_instance_id: str
    target_state: TargetStatus.TargetState
    def __init__(self, compute_instance_id: _Optional[str] = ..., target_state: _Optional[_Union[TargetStatus.TargetState, str]] = ...) -> None: ...
