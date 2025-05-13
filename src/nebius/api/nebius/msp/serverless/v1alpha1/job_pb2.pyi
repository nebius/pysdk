from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.msp.v1alpha1 import cluster_pb2 as _cluster_pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class JobResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    JOB_RESULT_UNSPECIFIED: _ClassVar[JobResult]
    JOB_RESULT_SUCCESS: _ClassVar[JobResult]
    JOB_RESULT_FAILURE: _ClassVar[JobResult]
    JOB_RESULT_CANCELLED: _ClassVar[JobResult]
JOB_RESULT_UNSPECIFIED: JobResult
JOB_RESULT_SUCCESS: JobResult
JOB_RESULT_FAILURE: JobResult
JOB_RESULT_CANCELLED: JobResult

class Job(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: JobSpec
    status: JobStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[JobSpec, _Mapping]] = ..., status: _Optional[_Union[JobStatus, _Mapping]] = ...) -> None: ...

class JobSpec(_message.Message):
    __slots__ = ["description", "network_id", "container"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_FIELD_NUMBER: _ClassVar[int]
    description: str
    network_id: str
    container: JobContainerSpec
    def __init__(self, description: _Optional[str] = ..., network_id: _Optional[str] = ..., container: _Optional[_Union[JobContainerSpec, _Mapping]] = ...) -> None: ...

class JobContainerSpec(_message.Message):
    __slots__ = ["image", "replica_count", "template", "command", "args", "envs", "sensitive_envs", "timeout_seconds", "max_retries"]
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
    TIMEOUT_SECONDS_FIELD_NUMBER: _ClassVar[int]
    MAX_RETRIES_FIELD_NUMBER: _ClassVar[int]
    image: str
    replica_count: int
    template: JobTemplateSpec
    command: str
    args: _containers.RepeatedScalarFieldContainer[str]
    envs: _containers.ScalarMap[str, str]
    sensitive_envs: _containers.ScalarMap[str, str]
    timeout_seconds: int
    max_retries: int
    def __init__(self, image: _Optional[str] = ..., replica_count: _Optional[int] = ..., template: _Optional[_Union[JobTemplateSpec, _Mapping]] = ..., command: _Optional[str] = ..., args: _Optional[_Iterable[str]] = ..., envs: _Optional[_Mapping[str, str]] = ..., sensitive_envs: _Optional[_Mapping[str, str]] = ..., timeout_seconds: _Optional[int] = ..., max_retries: _Optional[int] = ...) -> None: ...

class JobTemplateSpec(_message.Message):
    __slots__ = ["resources"]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    resources: _template_pb2.ResourcesSpec
    def __init__(self, resources: _Optional[_Union[_template_pb2.ResourcesSpec, _Mapping]] = ...) -> None: ...

class JobStatus(_message.Message):
    __slots__ = ["phase", "state", "result"]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    phase: _cluster_pb2.ClusterStatus.Phase
    state: _cluster_pb2.ClusterStatus.State
    result: JobResult
    def __init__(self, phase: _Optional[_Union[_cluster_pb2.ClusterStatus.Phase, str]] = ..., state: _Optional[_Union[_cluster_pb2.ClusterStatus.State, str]] = ..., result: _Optional[_Union[JobResult, str]] = ...) -> None: ...
