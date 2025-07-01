from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.storage.v1 import base_pb2 as _base_pb2
from nebius.api.nebius.storage.v1 import bucket_counters_pb2 as _bucket_counters_pb2
from nebius.api.nebius.storage.v1 import lifecycle_pb2 as _lifecycle_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Bucket(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: BucketSpec
    status: BucketStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[BucketSpec, _Mapping]] = ..., status: _Optional[_Union[BucketStatus, _Mapping]] = ...) -> None: ...

class BucketSpec(_message.Message):
    __slots__ = ["versioning_policy", "max_size_bytes", "lifecycle_configuration", "default_storage_class", "override_storage_class"]
    VERSIONING_POLICY_FIELD_NUMBER: _ClassVar[int]
    MAX_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    LIFECYCLE_CONFIGURATION_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
    versioning_policy: _base_pb2.VersioningPolicy
    max_size_bytes: int
    lifecycle_configuration: _lifecycle_pb2.LifecycleConfiguration
    default_storage_class: _base_pb2.StorageClass
    override_storage_class: _base_pb2.StorageClass
    def __init__(self, versioning_policy: _Optional[_Union[_base_pb2.VersioningPolicy, str]] = ..., max_size_bytes: _Optional[int] = ..., lifecycle_configuration: _Optional[_Union[_lifecycle_pb2.LifecycleConfiguration, _Mapping]] = ..., default_storage_class: _Optional[_Union[_base_pb2.StorageClass, str]] = ..., override_storage_class: _Optional[_Union[_base_pb2.StorageClass, str]] = ...) -> None: ...

class BucketStatus(_message.Message):
    __slots__ = ["counters", "state", "suspension_state", "deleted_at", "purge_at", "domain_name", "region"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[BucketStatus.State]
        CREATING: _ClassVar[BucketStatus.State]
        ACTIVE: _ClassVar[BucketStatus.State]
        UPDATING: _ClassVar[BucketStatus.State]
        SCHEDULED_FOR_DELETION: _ClassVar[BucketStatus.State]
    STATE_UNSPECIFIED: BucketStatus.State
    CREATING: BucketStatus.State
    ACTIVE: BucketStatus.State
    UPDATING: BucketStatus.State
    SCHEDULED_FOR_DELETION: BucketStatus.State
    class SuspensionState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        SUSPENSION_STATE_UNSPECIFIED: _ClassVar[BucketStatus.SuspensionState]
        NOT_SUSPENDED: _ClassVar[BucketStatus.SuspensionState]
        SUSPENDED: _ClassVar[BucketStatus.SuspensionState]
    SUSPENSION_STATE_UNSPECIFIED: BucketStatus.SuspensionState
    NOT_SUSPENDED: BucketStatus.SuspensionState
    SUSPENDED: BucketStatus.SuspensionState
    COUNTERS_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    SUSPENSION_STATE_FIELD_NUMBER: _ClassVar[int]
    DELETED_AT_FIELD_NUMBER: _ClassVar[int]
    PURGE_AT_FIELD_NUMBER: _ClassVar[int]
    DOMAIN_NAME_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    counters: _containers.RepeatedCompositeFieldContainer[_bucket_counters_pb2.BucketCounters]
    state: BucketStatus.State
    suspension_state: BucketStatus.SuspensionState
    deleted_at: _timestamp_pb2.Timestamp
    purge_at: _timestamp_pb2.Timestamp
    domain_name: str
    region: str
    def __init__(self, counters: _Optional[_Iterable[_Union[_bucket_counters_pb2.BucketCounters, _Mapping]]] = ..., state: _Optional[_Union[BucketStatus.State, str]] = ..., suspension_state: _Optional[_Union[BucketStatus.SuspensionState, str]] = ..., deleted_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., purge_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., domain_name: _Optional[str] = ..., region: _Optional[str] = ...) -> None: ...
