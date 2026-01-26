from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import resource_event_pb2 as _resource_event_pb2
from nebius.api.nebius.mk8s.v1 import instance_template_pb2 as _instance_template_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ConditionStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    CONDITION_STATUS_UNSPECIFIED: _ClassVar[ConditionStatus]
    TRUE: _ClassVar[ConditionStatus]
    FALSE: _ClassVar[ConditionStatus]
    UNKNOWN: _ClassVar[ConditionStatus]
CONDITION_STATUS_UNSPECIFIED: ConditionStatus
TRUE: ConditionStatus
FALSE: ConditionStatus
UNKNOWN: ConditionStatus

class NodeGroup(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: NodeGroupSpec
    status: NodeGroupStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[NodeGroupSpec, _Mapping]] = ..., status: _Optional[_Union[NodeGroupStatus, _Mapping]] = ...) -> None: ...

class NodeGroupSpec(_message.Message):
    __slots__ = ["version", "fixed_node_count", "autoscaling", "template", "strategy", "auto_repair"]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    FIXED_NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    AUTOSCALING_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    STRATEGY_FIELD_NUMBER: _ClassVar[int]
    AUTO_REPAIR_FIELD_NUMBER: _ClassVar[int]
    version: str
    fixed_node_count: int
    autoscaling: NodeGroupAutoscalingSpec
    template: NodeTemplate
    strategy: NodeGroupDeploymentStrategy
    auto_repair: NodeGroupAutoRepairSpec
    def __init__(self, version: _Optional[str] = ..., fixed_node_count: _Optional[int] = ..., autoscaling: _Optional[_Union[NodeGroupAutoscalingSpec, _Mapping]] = ..., template: _Optional[_Union[NodeTemplate, _Mapping]] = ..., strategy: _Optional[_Union[NodeGroupDeploymentStrategy, _Mapping]] = ..., auto_repair: _Optional[_Union[NodeGroupAutoRepairSpec, _Mapping]] = ...) -> None: ...

class NodeTemplate(_message.Message):
    __slots__ = ["metadata", "taints", "resources", "boot_disk", "gpu_settings", "os", "gpu_cluster", "network_interfaces", "filesystems", "cloud_init_user_data", "service_account_id", "preemptible", "reservation_policy"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    TAINTS_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    BOOT_DISK_FIELD_NUMBER: _ClassVar[int]
    GPU_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    OS_FIELD_NUMBER: _ClassVar[int]
    GPU_CLUSTER_FIELD_NUMBER: _ClassVar[int]
    NETWORK_INTERFACES_FIELD_NUMBER: _ClassVar[int]
    FILESYSTEMS_FIELD_NUMBER: _ClassVar[int]
    CLOUD_INIT_USER_DATA_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    PREEMPTIBLE_FIELD_NUMBER: _ClassVar[int]
    RESERVATION_POLICY_FIELD_NUMBER: _ClassVar[int]
    metadata: NodeMetadataTemplate
    taints: _containers.RepeatedCompositeFieldContainer[NodeTaint]
    resources: _instance_template_pb2.ResourcesSpec
    boot_disk: _instance_template_pb2.DiskSpec
    gpu_settings: GpuSettings
    os: str
    gpu_cluster: GpuClusterSpec
    network_interfaces: _containers.RepeatedCompositeFieldContainer[NetworkInterfaceTemplate]
    filesystems: _containers.RepeatedCompositeFieldContainer[AttachedFilesystemSpec]
    cloud_init_user_data: str
    service_account_id: str
    preemptible: PreemptibleSpec
    reservation_policy: ReservationPolicy
    def __init__(self, metadata: _Optional[_Union[NodeMetadataTemplate, _Mapping]] = ..., taints: _Optional[_Iterable[_Union[NodeTaint, _Mapping]]] = ..., resources: _Optional[_Union[_instance_template_pb2.ResourcesSpec, _Mapping]] = ..., boot_disk: _Optional[_Union[_instance_template_pb2.DiskSpec, _Mapping]] = ..., gpu_settings: _Optional[_Union[GpuSettings, _Mapping]] = ..., os: _Optional[str] = ..., gpu_cluster: _Optional[_Union[GpuClusterSpec, _Mapping]] = ..., network_interfaces: _Optional[_Iterable[_Union[NetworkInterfaceTemplate, _Mapping]]] = ..., filesystems: _Optional[_Iterable[_Union[AttachedFilesystemSpec, _Mapping]]] = ..., cloud_init_user_data: _Optional[str] = ..., service_account_id: _Optional[str] = ..., preemptible: _Optional[_Union[PreemptibleSpec, _Mapping]] = ..., reservation_policy: _Optional[_Union[ReservationPolicy, _Mapping]] = ...) -> None: ...

class NodeMetadataTemplate(_message.Message):
    __slots__ = ["labels"]
    class LabelsEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    LABELS_FIELD_NUMBER: _ClassVar[int]
    labels: _containers.ScalarMap[str, str]
    def __init__(self, labels: _Optional[_Mapping[str, str]] = ...) -> None: ...

class GpuSettings(_message.Message):
    __slots__ = ["drivers_preset"]
    DRIVERS_PRESET_FIELD_NUMBER: _ClassVar[int]
    drivers_preset: str
    def __init__(self, drivers_preset: _Optional[str] = ...) -> None: ...

class GpuClusterSpec(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class NetworkInterfaceTemplate(_message.Message):
    __slots__ = ["public_ip_address", "subnet_id"]
    PUBLIC_IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SUBNET_ID_FIELD_NUMBER: _ClassVar[int]
    public_ip_address: PublicIPAddress
    subnet_id: str
    def __init__(self, public_ip_address: _Optional[_Union[PublicIPAddress, _Mapping]] = ..., subnet_id: _Optional[str] = ...) -> None: ...

class PublicIPAddress(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

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

class ExistingFilesystem(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class NodeGroupAutoscalingSpec(_message.Message):
    __slots__ = ["min_node_count", "max_node_count"]
    MIN_NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    MAX_NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    min_node_count: int
    max_node_count: int
    def __init__(self, min_node_count: _Optional[int] = ..., max_node_count: _Optional[int] = ...) -> None: ...

class NodeTaint(_message.Message):
    __slots__ = ["key", "value", "effect"]
    class Effect(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        EFFECT_UNSPECIFIED: _ClassVar[NodeTaint.Effect]
        NO_EXECUTE: _ClassVar[NodeTaint.Effect]
        NO_SCHEDULE: _ClassVar[NodeTaint.Effect]
        PREFER_NO_SCHEDULE: _ClassVar[NodeTaint.Effect]
    EFFECT_UNSPECIFIED: NodeTaint.Effect
    NO_EXECUTE: NodeTaint.Effect
    NO_SCHEDULE: NodeTaint.Effect
    PREFER_NO_SCHEDULE: NodeTaint.Effect
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    EFFECT_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    effect: NodeTaint.Effect
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ..., effect: _Optional[_Union[NodeTaint.Effect, str]] = ...) -> None: ...

class NodeGroupDeploymentStrategy(_message.Message):
    __slots__ = ["max_unavailable", "max_surge", "drain_timeout"]
    MAX_UNAVAILABLE_FIELD_NUMBER: _ClassVar[int]
    MAX_SURGE_FIELD_NUMBER: _ClassVar[int]
    DRAIN_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    max_unavailable: PercentOrCount
    max_surge: PercentOrCount
    drain_timeout: _duration_pb2.Duration
    def __init__(self, max_unavailable: _Optional[_Union[PercentOrCount, _Mapping]] = ..., max_surge: _Optional[_Union[PercentOrCount, _Mapping]] = ..., drain_timeout: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class PercentOrCount(_message.Message):
    __slots__ = ["percent", "count"]
    PERCENT_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    percent: int
    count: int
    def __init__(self, percent: _Optional[int] = ..., count: _Optional[int] = ...) -> None: ...

class NodeGroupAutoRepairSpec(_message.Message):
    __slots__ = ["conditions"]
    CONDITIONS_FIELD_NUMBER: _ClassVar[int]
    conditions: _containers.RepeatedCompositeFieldContainer[NodeAutoRepairCondition]
    def __init__(self, conditions: _Optional[_Iterable[_Union[NodeAutoRepairCondition, _Mapping]]] = ...) -> None: ...

class NodeAutoRepairCondition(_message.Message):
    __slots__ = ["type", "status", "timeout", "disabled"]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    DISABLED_FIELD_NUMBER: _ClassVar[int]
    type: str
    status: ConditionStatus
    timeout: _duration_pb2.Duration
    disabled: bool
    def __init__(self, type: _Optional[str] = ..., status: _Optional[_Union[ConditionStatus, str]] = ..., timeout: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., disabled: bool = ...) -> None: ...

class PreemptibleSpec(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

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

class NodeGroupStatus(_message.Message):
    __slots__ = ["state", "version", "target_node_count", "node_count", "outdated_node_count", "ready_node_count", "events", "reconciling"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[NodeGroupStatus.State]
        PROVISIONING: _ClassVar[NodeGroupStatus.State]
        RUNNING: _ClassVar[NodeGroupStatus.State]
        DELETING: _ClassVar[NodeGroupStatus.State]
    STATE_UNSPECIFIED: NodeGroupStatus.State
    PROVISIONING: NodeGroupStatus.State
    RUNNING: NodeGroupStatus.State
    DELETING: NodeGroupStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    TARGET_NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    OUTDATED_NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    READY_NODE_COUNT_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    state: NodeGroupStatus.State
    version: str
    target_node_count: int
    node_count: int
    outdated_node_count: int
    ready_node_count: int
    events: _containers.RepeatedCompositeFieldContainer[_resource_event_pb2.RecurrentResourceEvent]
    reconciling: bool
    def __init__(self, state: _Optional[_Union[NodeGroupStatus.State, str]] = ..., version: _Optional[str] = ..., target_node_count: _Optional[int] = ..., node_count: _Optional[int] = ..., outdated_node_count: _Optional[int] = ..., ready_node_count: _Optional[int] = ..., events: _Optional[_Iterable[_Union[_resource_event_pb2.RecurrentResourceEvent, _Mapping]]] = ..., reconciling: bool = ...) -> None: ...
