from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.example.compute.v1alpha1 import testing_pb2 as _testing_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Instance(_message.Message):
    __slots__ = ("metadata", "spec", "status")
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: InstanceSpec
    status: InstanceStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[InstanceSpec, _Mapping]] = ..., status: _Optional[_Union[InstanceStatus, _Mapping]] = ...) -> None: ...

class InstanceSpec(_message.Message):
    __slots__ = ("instance_name", "description", "zone_id", "platform_id", "resources", "instance_metadata", "boot_disk_id", "secondary_disks", "network_interfaces", "hostname", "service_account_id", "testing")
    class InstanceMetadataEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    INSTANCE_NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ZONE_ID_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_METADATA_FIELD_NUMBER: _ClassVar[int]
    BOOT_DISK_ID_FIELD_NUMBER: _ClassVar[int]
    SECONDARY_DISKS_FIELD_NUMBER: _ClassVar[int]
    NETWORK_INTERFACES_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    TESTING_FIELD_NUMBER: _ClassVar[int]
    instance_name: str
    description: str
    zone_id: str
    platform_id: str
    resources: Resources
    instance_metadata: _containers.ScalarMap[str, str]
    boot_disk_id: str
    secondary_disks: _containers.RepeatedScalarFieldContainer[str]
    network_interfaces: _containers.RepeatedScalarFieldContainer[str]
    hostname: str
    service_account_id: str
    testing: _testing_pb2.TestingSpec
    def __init__(self, instance_name: _Optional[str] = ..., description: _Optional[str] = ..., zone_id: _Optional[str] = ..., platform_id: _Optional[str] = ..., resources: _Optional[_Union[Resources, _Mapping]] = ..., instance_metadata: _Optional[_Mapping[str, str]] = ..., boot_disk_id: _Optional[str] = ..., secondary_disks: _Optional[_Iterable[str]] = ..., network_interfaces: _Optional[_Iterable[str]] = ..., hostname: _Optional[str] = ..., service_account_id: _Optional[str] = ..., testing: _Optional[_Union[_testing_pb2.TestingSpec, _Mapping]] = ...) -> None: ...

class Resources(_message.Message):
    __slots__ = ("memory_bytes", "cores_count")
    MEMORY_BYTES_FIELD_NUMBER: _ClassVar[int]
    CORES_COUNT_FIELD_NUMBER: _ClassVar[int]
    memory_bytes: int
    cores_count: int
    def __init__(self, memory_bytes: _Optional[int] = ..., cores_count: _Optional[int] = ...) -> None: ...

class InstanceStatus(_message.Message):
    __slots__ = ("state", "compute_node", "reconciling")
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_UNSPECIFIED: _ClassVar[InstanceStatus.State]
        PROVISIONING: _ClassVar[InstanceStatus.State]
        RUNNING: _ClassVar[InstanceStatus.State]
        STOPPING: _ClassVar[InstanceStatus.State]
        STOPPED: _ClassVar[InstanceStatus.State]
        STARTING: _ClassVar[InstanceStatus.State]
        RESTARTING: _ClassVar[InstanceStatus.State]
        UPDATING: _ClassVar[InstanceStatus.State]
        ERROR: _ClassVar[InstanceStatus.State]
        CRASHED: _ClassVar[InstanceStatus.State]
        DELETING: _ClassVar[InstanceStatus.State]
    STATUS_UNSPECIFIED: InstanceStatus.State
    PROVISIONING: InstanceStatus.State
    RUNNING: InstanceStatus.State
    STOPPING: InstanceStatus.State
    STOPPED: InstanceStatus.State
    STARTING: InstanceStatus.State
    RESTARTING: InstanceStatus.State
    UPDATING: InstanceStatus.State
    ERROR: InstanceStatus.State
    CRASHED: InstanceStatus.State
    DELETING: InstanceStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_NODE_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    state: InstanceStatus.State
    compute_node: str
    reconciling: bool
    def __init__(self, state: _Optional[_Union[InstanceStatus.State, str]] = ..., compute_node: _Optional[str] = ..., reconciling: bool = ...) -> None: ...
