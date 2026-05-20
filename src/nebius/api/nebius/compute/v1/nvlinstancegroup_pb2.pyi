from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.compute.v1 import instance_pb2 as _instance_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class NVLInstanceGroup(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: NVLInstanceGroupSpec
    status: NVLInstanceGroupStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[NVLInstanceGroupSpec, _Mapping]] = ..., status: _Optional[_Union[NVLInstanceGroupStatus, _Mapping]] = ...) -> None: ...

class NVLInstanceGroupSpec(_message.Message):
    __slots__ = ["type"]
    class NVLInstanceGroupType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[NVLInstanceGroupSpec.NVLInstanceGroupType]
        GB200: _ClassVar[NVLInstanceGroupSpec.NVLInstanceGroupType]
        GB300: _ClassVar[NVLInstanceGroupSpec.NVLInstanceGroupType]
    UNSPECIFIED: NVLInstanceGroupSpec.NVLInstanceGroupType
    GB200: NVLInstanceGroupSpec.NVLInstanceGroupType
    GB300: NVLInstanceGroupSpec.NVLInstanceGroupType
    TYPE_FIELD_NUMBER: _ClassVar[int]
    type: NVLInstanceGroupSpec.NVLInstanceGroupType
    def __init__(self, type: _Optional[_Union[NVLInstanceGroupSpec.NVLInstanceGroupType, str]] = ...) -> None: ...

class NVLInstanceGroupStatus(_message.Message):
    __slots__ = ["instances", "reconciling"]
    class InstanceInfo(_message.Message):
        __slots__ = ["instance_state"]
        INSTANCE_STATE_FIELD_NUMBER: _ClassVar[int]
        instance_state: _instance_pb2.InstanceStatus.InstanceState
        def __init__(self, instance_state: _Optional[_Union[_instance_pb2.InstanceStatus.InstanceState, str]] = ...) -> None: ...
    class InstancesEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: NVLInstanceGroupStatus.InstanceInfo
        def __init__(self, key: _Optional[str] = ..., value: _Optional[_Union[NVLInstanceGroupStatus.InstanceInfo, _Mapping]] = ...) -> None: ...
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    instances: _containers.MessageMap[str, NVLInstanceGroupStatus.InstanceInfo]
    reconciling: bool
    def __init__(self, instances: _Optional[_Mapping[str, NVLInstanceGroupStatus.InstanceInfo]] = ..., reconciling: bool = ...) -> None: ...
