from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

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
    __slots__ = ["control_plane", "kube_network"]
    CONTROL_PLANE_FIELD_NUMBER: _ClassVar[int]
    KUBE_NETWORK_FIELD_NUMBER: _ClassVar[int]
    control_plane: ControlPlaneSpec
    kube_network: KubeNetworkSpec
    def __init__(self, control_plane: _Optional[_Union[ControlPlaneSpec, _Mapping]] = ..., kube_network: _Optional[_Union[KubeNetworkSpec, _Mapping]] = ...) -> None: ...

class ControlPlaneSpec(_message.Message):
    __slots__ = ["version", "subnet_id", "endpoints", "etcd_cluster_size"]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    SUBNET_ID_FIELD_NUMBER: _ClassVar[int]
    ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    ETCD_CLUSTER_SIZE_FIELD_NUMBER: _ClassVar[int]
    version: str
    subnet_id: str
    endpoints: ControlPlaneEndpointsSpec
    etcd_cluster_size: int
    def __init__(self, version: _Optional[str] = ..., subnet_id: _Optional[str] = ..., endpoints: _Optional[_Union[ControlPlaneEndpointsSpec, _Mapping]] = ..., etcd_cluster_size: _Optional[int] = ...) -> None: ...

class ControlPlaneEndpointsSpec(_message.Message):
    __slots__ = ["public_endpoint"]
    PUBLIC_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    public_endpoint: PublicEndpointSpec
    def __init__(self, public_endpoint: _Optional[_Union[PublicEndpointSpec, _Mapping]] = ...) -> None: ...

class PublicEndpointSpec(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class KubeNetworkSpec(_message.Message):
    __slots__ = ["service_cidrs"]
    SERVICE_CIDRS_FIELD_NUMBER: _ClassVar[int]
    service_cidrs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, service_cidrs: _Optional[_Iterable[str]] = ...) -> None: ...

class ClusterStatus(_message.Message):
    __slots__ = ["state", "control_plane", "reconciling"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[ClusterStatus.State]
        PROVISIONING: _ClassVar[ClusterStatus.State]
        RUNNING: _ClassVar[ClusterStatus.State]
        DELETING: _ClassVar[ClusterStatus.State]
    STATE_UNSPECIFIED: ClusterStatus.State
    PROVISIONING: ClusterStatus.State
    RUNNING: ClusterStatus.State
    DELETING: ClusterStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    CONTROL_PLANE_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    state: ClusterStatus.State
    control_plane: ControlPlaneStatus
    reconciling: bool
    def __init__(self, state: _Optional[_Union[ClusterStatus.State, str]] = ..., control_plane: _Optional[_Union[ControlPlaneStatus, _Mapping]] = ..., reconciling: bool = ...) -> None: ...

class ControlPlaneStatus(_message.Message):
    __slots__ = ["version", "endpoints", "etcd_cluster_size", "auth"]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    ETCD_CLUSTER_SIZE_FIELD_NUMBER: _ClassVar[int]
    AUTH_FIELD_NUMBER: _ClassVar[int]
    version: str
    endpoints: ControlPlaneStatusEndpoints
    etcd_cluster_size: int
    auth: ControlPlaneStatusAuth
    def __init__(self, version: _Optional[str] = ..., endpoints: _Optional[_Union[ControlPlaneStatusEndpoints, _Mapping]] = ..., etcd_cluster_size: _Optional[int] = ..., auth: _Optional[_Union[ControlPlaneStatusAuth, _Mapping]] = ...) -> None: ...

class ControlPlaneStatusEndpoints(_message.Message):
    __slots__ = ["public_endpoint", "private_endpoint"]
    PUBLIC_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    public_endpoint: str
    private_endpoint: str
    def __init__(self, public_endpoint: _Optional[str] = ..., private_endpoint: _Optional[str] = ...) -> None: ...

class ControlPlaneStatusAuth(_message.Message):
    __slots__ = ["cluster_ca_certificate"]
    CLUSTER_CA_CERTIFICATE_FIELD_NUMBER: _ClassVar[int]
    cluster_ca_certificate: str
    def __init__(self, cluster_ca_certificate: _Optional[str] = ...) -> None: ...
