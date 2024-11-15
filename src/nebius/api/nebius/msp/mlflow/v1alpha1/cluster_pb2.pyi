from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.msp.v1alpha1 import cluster_pb2 as _cluster_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Cluster(_message.Message):
    __slots__ = ("metadata", "spec", "status")
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ClusterSpec
    status: MlflowClusterStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ClusterSpec, _Mapping]] = ..., status: _Optional[_Union[MlflowClusterStatus, _Mapping]] = ...) -> None: ...

class ClusterSpec(_message.Message):
    __slots__ = ("description", "public_access", "admin_username", "admin_password", "service_account_id", "storage_bucket_name", "network_id")
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_ACCESS_FIELD_NUMBER: _ClassVar[int]
    ADMIN_USERNAME_FIELD_NUMBER: _ClassVar[int]
    ADMIN_PASSWORD_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    STORAGE_BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    description: str
    public_access: bool
    admin_username: str
    admin_password: str
    service_account_id: str
    storage_bucket_name: str
    network_id: str
    def __init__(self, description: _Optional[str] = ..., public_access: bool = ..., admin_username: _Optional[str] = ..., admin_password: _Optional[str] = ..., service_account_id: _Optional[str] = ..., storage_bucket_name: _Optional[str] = ..., network_id: _Optional[str] = ...) -> None: ...

class MlflowClusterStatus(_message.Message):
    __slots__ = ("phase", "state", "tracking_endpoint", "effective_storage_bucket_name", "experiments_count", "mlflow_version")
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    TRACKING_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_STORAGE_BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    EXPERIMENTS_COUNT_FIELD_NUMBER: _ClassVar[int]
    MLFLOW_VERSION_FIELD_NUMBER: _ClassVar[int]
    phase: _cluster_pb2.ClusterStatus.Phase
    state: _cluster_pb2.ClusterStatus.State
    tracking_endpoint: str
    effective_storage_bucket_name: str
    experiments_count: int
    mlflow_version: str
    def __init__(self, phase: _Optional[_Union[_cluster_pb2.ClusterStatus.Phase, str]] = ..., state: _Optional[_Union[_cluster_pb2.ClusterStatus.State, str]] = ..., tracking_endpoint: _Optional[str] = ..., effective_storage_bucket_name: _Optional[str] = ..., experiments_count: _Optional[int] = ..., mlflow_version: _Optional[str] = ...) -> None: ...
