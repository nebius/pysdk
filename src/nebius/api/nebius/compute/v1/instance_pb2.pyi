from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.compute.v1 import network_interface_pb2 as _network_interface_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InstanceRecoveryPolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    RECOVER: _ClassVar[InstanceRecoveryPolicy]
    FAIL: _ClassVar[InstanceRecoveryPolicy]
RECOVER: InstanceRecoveryPolicy
FAIL: InstanceRecoveryPolicy

class Instance(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: InstanceSpec
    status: InstanceStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[InstanceSpec, _Mapping]] = ..., status: _Optional[_Union[InstanceStatus, _Mapping]] = ...) -> None: ...

class InstanceSpec(_message.Message):
    __slots__ = ["service_account_id", "resources", "gpu_cluster", "network_interfaces", "boot_disk", "secondary_disks", "filesystems", "cloud_init_user_data", "stopped", "recovery_policy", "preemptible", "hostname", "reservation_policy"]
    SERVICE_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    GPU_CLUSTER_FIELD_NUMBER: _ClassVar[int]
    NETWORK_INTERFACES_FIELD_NUMBER: _ClassVar[int]
    BOOT_DISK_FIELD_NUMBER: _ClassVar[int]
    SECONDARY_DISKS_FIELD_NUMBER: _ClassVar[int]
    FILESYSTEMS_FIELD_NUMBER: _ClassVar[int]
    CLOUD_INIT_USER_DATA_FIELD_NUMBER: _ClassVar[int]
    STOPPED_FIELD_NUMBER: _ClassVar[int]
    RECOVERY_POLICY_FIELD_NUMBER: _ClassVar[int]
    PREEMPTIBLE_FIELD_NUMBER: _ClassVar[int]
    HOSTNAME_FIELD_NUMBER: _ClassVar[int]
    RESERVATION_POLICY_FIELD_NUMBER: _ClassVar[int]
    service_account_id: str
    resources: ResourcesSpec
    gpu_cluster: InstanceGpuClusterSpec
    network_interfaces: _containers.RepeatedCompositeFieldContainer[_network_interface_pb2.NetworkInterfaceSpec]
    boot_disk: AttachedDiskSpec
    secondary_disks: _containers.RepeatedCompositeFieldContainer[AttachedDiskSpec]
    filesystems: _containers.RepeatedCompositeFieldContainer[AttachedFilesystemSpec]
    cloud_init_user_data: str
    stopped: bool
    recovery_policy: InstanceRecoveryPolicy
    preemptible: PreemptibleSpec
    hostname: str
    reservation_policy: ReservationPolicy
    def __init__(self, service_account_id: _Optional[str] = ..., resources: _Optional[_Union[ResourcesSpec, _Mapping]] = ..., gpu_cluster: _Optional[_Union[InstanceGpuClusterSpec, _Mapping]] = ..., network_interfaces: _Optional[_Iterable[_Union[_network_interface_pb2.NetworkInterfaceSpec, _Mapping]]] = ..., boot_disk: _Optional[_Union[AttachedDiskSpec, _Mapping]] = ..., secondary_disks: _Optional[_Iterable[_Union[AttachedDiskSpec, _Mapping]]] = ..., filesystems: _Optional[_Iterable[_Union[AttachedFilesystemSpec, _Mapping]]] = ..., cloud_init_user_data: _Optional[str] = ..., stopped: bool = ..., recovery_policy: _Optional[_Union[InstanceRecoveryPolicy, str]] = ..., preemptible: _Optional[_Union[PreemptibleSpec, _Mapping]] = ..., hostname: _Optional[str] = ..., reservation_policy: _Optional[_Union[ReservationPolicy, _Mapping]] = ...) -> None: ...

class PreemptibleSpec(_message.Message):
    __slots__ = ["on_preemption", "priority"]
    class PreemptionPolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[PreemptibleSpec.PreemptionPolicy]
        STOP: _ClassVar[PreemptibleSpec.PreemptionPolicy]
    UNSPECIFIED: PreemptibleSpec.PreemptionPolicy
    STOP: PreemptibleSpec.PreemptionPolicy
    ON_PREEMPTION_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    on_preemption: PreemptibleSpec.PreemptionPolicy
    priority: int
    def __init__(self, on_preemption: _Optional[_Union[PreemptibleSpec.PreemptionPolicy, str]] = ..., priority: _Optional[int] = ...) -> None: ...

class ResourcesSpec(_message.Message):
    __slots__ = ["platform", "preset"]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    PRESET_FIELD_NUMBER: _ClassVar[int]
    platform: str
    preset: str
    def __init__(self, platform: _Optional[str] = ..., preset: _Optional[str] = ...) -> None: ...

class InstanceGpuClusterSpec(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class AttachedDiskSpec(_message.Message):
    __slots__ = ["attach_mode", "existing_disk", "device_id"]
    class AttachMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[AttachedDiskSpec.AttachMode]
        READ_ONLY: _ClassVar[AttachedDiskSpec.AttachMode]
        READ_WRITE: _ClassVar[AttachedDiskSpec.AttachMode]
    UNSPECIFIED: AttachedDiskSpec.AttachMode
    READ_ONLY: AttachedDiskSpec.AttachMode
    READ_WRITE: AttachedDiskSpec.AttachMode
    ATTACH_MODE_FIELD_NUMBER: _ClassVar[int]
    EXISTING_DISK_FIELD_NUMBER: _ClassVar[int]
    DEVICE_ID_FIELD_NUMBER: _ClassVar[int]
    attach_mode: AttachedDiskSpec.AttachMode
    existing_disk: ExistingDisk
    device_id: str
    def __init__(self, attach_mode: _Optional[_Union[AttachedDiskSpec.AttachMode, str]] = ..., existing_disk: _Optional[_Union[ExistingDisk, _Mapping]] = ..., device_id: _Optional[str] = ...) -> None: ...

class ExistingDisk(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ExistingFilesystem(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class AttachedFilesystemSpec(_message.Message):
    __slots__ = ["attach_mode", "mount_tag", "existing_filesystem"]
    class AttachMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[AttachedFilesystemSpec.AttachMode]
        READ_ONLY: _ClassVar[AttachedFilesystemSpec.AttachMode]
        READ_WRITE: _ClassVar[AttachedFilesystemSpec.AttachMode]
    UNSPECIFIED: AttachedFilesystemSpec.AttachMode
    READ_ONLY: AttachedFilesystemSpec.AttachMode
    READ_WRITE: AttachedFilesystemSpec.AttachMode
    ATTACH_MODE_FIELD_NUMBER: _ClassVar[int]
    MOUNT_TAG_FIELD_NUMBER: _ClassVar[int]
    EXISTING_FILESYSTEM_FIELD_NUMBER: _ClassVar[int]
    attach_mode: AttachedFilesystemSpec.AttachMode
    mount_tag: str
    existing_filesystem: ExistingFilesystem
    def __init__(self, attach_mode: _Optional[_Union[AttachedFilesystemSpec.AttachMode, str]] = ..., mount_tag: _Optional[str] = ..., existing_filesystem: _Optional[_Union[ExistingFilesystem, _Mapping]] = ...) -> None: ...

class InstanceStatus(_message.Message):
    __slots__ = ["state", "network_interfaces", "reconciling", "maintenance_event_id", "infiniband_topology_path", "reservation_id"]
    class InstanceState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[InstanceStatus.InstanceState]
        CREATING: _ClassVar[InstanceStatus.InstanceState]
        UPDATING: _ClassVar[InstanceStatus.InstanceState]
        STARTING: _ClassVar[InstanceStatus.InstanceState]
        RUNNING: _ClassVar[InstanceStatus.InstanceState]
        STOPPING: _ClassVar[InstanceStatus.InstanceState]
        STOPPED: _ClassVar[InstanceStatus.InstanceState]
        DELETING: _ClassVar[InstanceStatus.InstanceState]
        ERROR: _ClassVar[InstanceStatus.InstanceState]
    UNSPECIFIED: InstanceStatus.InstanceState
    CREATING: InstanceStatus.InstanceState
    UPDATING: InstanceStatus.InstanceState
    STARTING: InstanceStatus.InstanceState
    RUNNING: InstanceStatus.InstanceState
    STOPPING: InstanceStatus.InstanceState
    STOPPED: InstanceStatus.InstanceState
    DELETING: InstanceStatus.InstanceState
    ERROR: InstanceStatus.InstanceState
    STATE_FIELD_NUMBER: _ClassVar[int]
    NETWORK_INTERFACES_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    MAINTENANCE_EVENT_ID_FIELD_NUMBER: _ClassVar[int]
    INFINIBAND_TOPOLOGY_PATH_FIELD_NUMBER: _ClassVar[int]
    RESERVATION_ID_FIELD_NUMBER: _ClassVar[int]
    state: InstanceStatus.InstanceState
    network_interfaces: _containers.RepeatedCompositeFieldContainer[_network_interface_pb2.NetworkInterfaceStatus]
    reconciling: bool
    maintenance_event_id: str
    infiniband_topology_path: InstanceStatusInfinibandTopologyPath
    reservation_id: str
    def __init__(self, state: _Optional[_Union[InstanceStatus.InstanceState, str]] = ..., network_interfaces: _Optional[_Iterable[_Union[_network_interface_pb2.NetworkInterfaceStatus, _Mapping]]] = ..., reconciling: bool = ..., maintenance_event_id: _Optional[str] = ..., infiniband_topology_path: _Optional[_Union[InstanceStatusInfinibandTopologyPath, _Mapping]] = ..., reservation_id: _Optional[str] = ...) -> None: ...

class InstanceStatusInfinibandTopologyPath(_message.Message):
    __slots__ = ["path"]
    PATH_FIELD_NUMBER: _ClassVar[int]
    path: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, path: _Optional[_Iterable[str]] = ...) -> None: ...

class ReservationPolicy(_message.Message):
    __slots__ = ["policy", "reservation_ids"]
    class Policy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        AUTO: _ClassVar[ReservationPolicy.Policy]
        FORBID: _ClassVar[ReservationPolicy.Policy]
        STRICT: _ClassVar[ReservationPolicy.Policy]
    AUTO: ReservationPolicy.Policy
    FORBID: ReservationPolicy.Policy
    STRICT: ReservationPolicy.Policy
    POLICY_FIELD_NUMBER: _ClassVar[int]
    RESERVATION_IDS_FIELD_NUMBER: _ClassVar[int]
    policy: ReservationPolicy.Policy
    reservation_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, policy: _Optional[_Union[ReservationPolicy.Policy, str]] = ..., reservation_ids: _Optional[_Iterable[str]] = ...) -> None: ...
