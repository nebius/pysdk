from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.msp.v1alpha1 import cluster_pb2 as _cluster_pb2
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

class ClusterSpec(_message.Message):
    __slots__ = ["description", "limits", "authorization", "service_account_id", "network_id"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    AUTHORIZATION_FIELD_NUMBER: _ClassVar[int]
    SERVICE_ACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    description: str
    limits: Limits
    authorization: Password
    service_account_id: str
    network_id: str
    def __init__(self, description: _Optional[str] = ..., limits: _Optional[_Union[Limits, _Mapping]] = ..., authorization: _Optional[_Union[Password, _Mapping]] = ..., service_account_id: _Optional[str] = ..., network_id: _Optional[str] = ...) -> None: ...

class ClusterStatus(_message.Message):
    __slots__ = ["phase", "state", "history_server_endpoint"]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    HISTORY_SERVER_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    phase: _cluster_pb2.ClusterStatus.Phase
    state: _cluster_pb2.ClusterStatus.State
    history_server_endpoint: str
    def __init__(self, phase: _Optional[_Union[_cluster_pb2.ClusterStatus.Phase, str]] = ..., state: _Optional[_Union[_cluster_pb2.ClusterStatus.State, str]] = ..., history_server_endpoint: _Optional[str] = ...) -> None: ...

class Limits(_message.Message):
    __slots__ = ["cpu", "memory_gibibytes"]
    CPU_FIELD_NUMBER: _ClassVar[int]
    MEMORY_GIBIBYTES_FIELD_NUMBER: _ClassVar[int]
    cpu: int
    memory_gibibytes: int
    def __init__(self, cpu: _Optional[int] = ..., memory_gibibytes: _Optional[int] = ...) -> None: ...

class Password(_message.Message):
    __slots__ = ["password"]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    password: str
    def __init__(self, password: _Optional[str] = ...) -> None: ...
