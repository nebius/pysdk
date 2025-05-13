from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.msp.v1alpha1 import cluster_pb2 as _cluster_pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Endpoint(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: EndpointSpec
    status: EndpointStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[EndpointSpec, _Mapping]] = ..., status: _Optional[_Union[EndpointStatus, _Mapping]] = ...) -> None: ...

class EndpointSpec(_message.Message):
    __slots__ = ["description", "network_id", "username", "password", "port", "container"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    PORT_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    description: str
    network_id: str
    username: str
    password: str
    port: int
    container: EndpointContainerSpec
    def __init__(self, description: _Optional[str] = ..., network_id: _Optional[str] = ..., username: _Optional[str] = ..., password: _Optional[str] = ..., port: _Optional[int] = ..., container: _Optional[_Union[EndpointContainerSpec, _Mapping]] = ...) -> None: ...

class EndpointContainerSpec(_message.Message):
    __slots__ = ["image", "replica_count", "template", "command", "args", "envs", "sensitive_envs", "liveness"]
    class EnvsEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    class SensitiveEnvsEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    REPLICA_COUNT_FIELD_NUMBER: _ClassVar[int]
    TEMPLATE_FIELD_NUMBER: _ClassVar[int]
    COMMAND_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    ENVS_FIELD_NUMBER: _ClassVar[int]
    SENSITIVE_ENVS_FIELD_NUMBER: _ClassVar[int]
    LIVENESS_FIELD_NUMBER: _ClassVar[int]
    image: str
    replica_count: int
    template: EndpointTemplateSpec
    command: str
    args: _containers.RepeatedScalarFieldContainer[str]
    envs: _containers.ScalarMap[str, str]
    sensitive_envs: _containers.ScalarMap[str, str]
    liveness: ProbeSpec
    def __init__(self, image: _Optional[str] = ..., replica_count: _Optional[int] = ..., template: _Optional[_Union[EndpointTemplateSpec, _Mapping]] = ..., command: _Optional[str] = ..., args: _Optional[_Iterable[str]] = ..., envs: _Optional[_Mapping[str, str]] = ..., sensitive_envs: _Optional[_Mapping[str, str]] = ..., liveness: _Optional[_Union[ProbeSpec, _Mapping]] = ...) -> None: ...

class ProbeSpec(_message.Message):
    __slots__ = ["path", "delay_seconds", "period_seconds", "failure_threshold"]
    PATH_FIELD_NUMBER: _ClassVar[int]
    DELAY_SECONDS_FIELD_NUMBER: _ClassVar[int]
    PERIOD_SECONDS_FIELD_NUMBER: _ClassVar[int]
    FAILURE_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    path: str
    delay_seconds: int
    period_seconds: int
    failure_threshold: int
    def __init__(self, path: _Optional[str] = ..., delay_seconds: _Optional[int] = ..., period_seconds: _Optional[int] = ..., failure_threshold: _Optional[int] = ...) -> None: ...

class EndpointTemplateSpec(_message.Message):
    __slots__ = ["resources"]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    resources: _template_pb2.ResourcesSpec
    def __init__(self, resources: _Optional[_Union[_template_pb2.ResourcesSpec, _Mapping]] = ...) -> None: ...

class EndpointStatus(_message.Message):
    __slots__ = ["phase", "state", "public_endpoint"]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    phase: _cluster_pb2.ClusterStatus.Phase
    state: _cluster_pb2.ClusterStatus.State
    public_endpoint: str
    def __init__(self, phase: _Optional[_Union[_cluster_pb2.ClusterStatus.Phase, str]] = ..., state: _Optional[_Union[_cluster_pb2.ClusterStatus.State, str]] = ..., public_endpoint: _Optional[str] = ...) -> None: ...
