from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.msp.v1alpha1 import cluster_pb2 as _cluster_pb2
from nebius.api.nebius.msp.postgresql.v1alpha1.config import postgresql_pb2 as _postgresql_pb2
from nebius.api.nebius.msp.postgresql.v1alpha1 import template_pb2 as _template_pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2_1
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Cluster(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ClusterSpec
    status: ClusterStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ClusterSpec, _Mapping]] = ..., status: _Optional[_Union[ClusterStatus, _Mapping]] = ...) -> None: ...

class ConnectionPoolerConfig(_message.Message):
    __slots__ = ["pooling_mode", "max_pool_size"]
    class PoolingMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        POOLING_MODE_UNSPECIFIED: _ClassVar[ConnectionPoolerConfig.PoolingMode]
        SESSION: _ClassVar[ConnectionPoolerConfig.PoolingMode]
        TRANSACTION: _ClassVar[ConnectionPoolerConfig.PoolingMode]
    POOLING_MODE_UNSPECIFIED: ConnectionPoolerConfig.PoolingMode
    SESSION: ConnectionPoolerConfig.PoolingMode
    TRANSACTION: ConnectionPoolerConfig.PoolingMode
    POOLING_MODE_FIELD_NUMBER: _ClassVar[int]
    MAX_POOL_SIZE_FIELD_NUMBER: _ClassVar[int]
    pooling_mode: ConnectionPoolerConfig.PoolingMode
    max_pool_size: int
    def __init__(self, pooling_mode: _Optional[_Union[ConnectionPoolerConfig.PoolingMode, str]] = ..., max_pool_size: _Optional[int] = ...) -> None: ...

class ClusterSpec(_message.Message):
    __slots__ = ["description", "network_id", "config", "bootstrap", "backup"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    BOOTSTRAP_FIELD_NUMBER: _ClassVar[int]
    BACKUP_FIELD_NUMBER: _ClassVar[int]
    description: str
    network_id: str
    config: ConfigSpec
    bootstrap: BootstrapSpec
    backup: BackupSpec
    def __init__(self, description: _Optional[str] = ..., network_id: _Optional[str] = ..., config: _Optional[_Union[ConfigSpec, _Mapping]] = ..., bootstrap: _Optional[_Union[BootstrapSpec, _Mapping]] = ..., backup: _Optional[_Union[BackupSpec, _Mapping]] = ...) -> None: ...

class ClusterStatus(_message.Message):
    __slots__ = ["phase", "state", "preset_details", "connection_endpoints"]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PRESET_DETAILS_FIELD_NUMBER: _ClassVar[int]
    CONNECTION_ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    phase: _cluster_pb2.ClusterStatus.Phase
    state: _cluster_pb2.ClusterStatus.State
    preset_details: _template_pb2_1.PresetDetails
    connection_endpoints: Endpoints
    def __init__(self, phase: _Optional[_Union[_cluster_pb2.ClusterStatus.Phase, str]] = ..., state: _Optional[_Union[_cluster_pb2.ClusterStatus.State, str]] = ..., preset_details: _Optional[_Union[_template_pb2_1.PresetDetails, _Mapping]] = ..., connection_endpoints: _Optional[_Union[Endpoints, _Mapping]] = ...) -> None: ...

class Endpoints(_message.Message):
    __slots__ = ["private_read_write", "private_read_only", "public_read_write", "public_read_only"]
    PRIVATE_READ_WRITE_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_READ_ONLY_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_READ_WRITE_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_READ_ONLY_FIELD_NUMBER: _ClassVar[int]
    private_read_write: str
    private_read_only: str
    public_read_write: str
    public_read_only: str
    def __init__(self, private_read_write: _Optional[str] = ..., private_read_only: _Optional[str] = ..., public_read_write: _Optional[str] = ..., public_read_only: _Optional[str] = ...) -> None: ...

class ConfigSpec(_message.Message):
    __slots__ = ["version", "pooler_config", "postgresql_config_16", "public_access", "template"]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    POOLER_CONFIG_FIELD_NUMBER: _ClassVar[int]
    POSTGRESQL_CONFIG_16_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_ACCESS_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    version: str
    pooler_config: ConnectionPoolerConfig
    postgresql_config_16: _postgresql_pb2.PostgresqlConfig16
    public_access: bool
    template: _template_pb2.TemplateSpec
    def __init__(self, version: _Optional[str] = ..., pooler_config: _Optional[_Union[ConnectionPoolerConfig, _Mapping]] = ..., postgresql_config_16: _Optional[_Union[_postgresql_pb2.PostgresqlConfig16, _Mapping]] = ..., public_access: bool = ..., template: _Optional[_Union[_template_pb2.TemplateSpec, _Mapping]] = ...) -> None: ...

class BootstrapSpec(_message.Message):
    __slots__ = ["user_name", "user_password", "db_name"]
    USER_NAME_FIELD_NUMBER: _ClassVar[int]
    USER_PASSWORD_FIELD_NUMBER: _ClassVar[int]
    DB_NAME_FIELD_NUMBER: _ClassVar[int]
    user_name: str
    user_password: str
    db_name: str
    def __init__(self, user_name: _Optional[str] = ..., user_password: _Optional[str] = ..., db_name: _Optional[str] = ...) -> None: ...

class BackupSpec(_message.Message):
    __slots__ = ["backup_window_start", "retention_policy"]
    BACKUP_WINDOW_START_FIELD_NUMBER: _ClassVar[int]
    RETENTION_POLICY_FIELD_NUMBER: _ClassVar[int]
    backup_window_start: str
    retention_policy: str
    def __init__(self, backup_window_start: _Optional[str] = ..., retention_policy: _Optional[str] = ...) -> None: ...
