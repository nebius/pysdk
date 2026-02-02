from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.compute.v1 import disk_pb2 as _disk_pb2
from nebius.api.nebius.compute.v1 import instance_pb2 as _instance_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

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
    __slots__ = ["image", "environment_variables", "ports", "container_command", "args", "working_dir", "volumes", "registry_credentials", "platform", "preset", "shm_size_bytes", "disk", "subnet_id", "public_ip", "ssh_authorized_keys", "restart_attempts", "timeout"]
    class EnvironmentVariable(_message.Message):
        __slots__ = ["name", "value"]
        NAME_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        name: str
        value: str
        def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    class Port(_message.Message):
        __slots__ = ["container_port", "host_port", "protocol"]
        class Protocol(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = []
            PROTOCOL_UNSPECIFIED: _ClassVar[JobSpec.Port.Protocol]
            HTTP: _ClassVar[JobSpec.Port.Protocol]
            TCP: _ClassVar[JobSpec.Port.Protocol]
            UDP: _ClassVar[JobSpec.Port.Protocol]
        PROTOCOL_UNSPECIFIED: JobSpec.Port.Protocol
        HTTP: JobSpec.Port.Protocol
        TCP: JobSpec.Port.Protocol
        UDP: JobSpec.Port.Protocol
        CONTAINER_PORT_FIELD_NUMBER: _ClassVar[int]
        HOST_PORT_FIELD_NUMBER: _ClassVar[int]
        PROTOCOL_FIELD_NUMBER: _ClassVar[int]
        container_port: int
        host_port: int
        protocol: JobSpec.Port.Protocol
        def __init__(self, container_port: _Optional[int] = ..., host_port: _Optional[int] = ..., protocol: _Optional[_Union[JobSpec.Port.Protocol, str]] = ...) -> None: ...
    class VolumeMount(_message.Message):
        __slots__ = ["source", "source_path", "container_path", "mode"]
        class Mode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = []
            MODE_UNSPECIFIED: _ClassVar[JobSpec.VolumeMount.Mode]
            READ_WRITE: _ClassVar[JobSpec.VolumeMount.Mode]
            READ_ONLY: _ClassVar[JobSpec.VolumeMount.Mode]
        MODE_UNSPECIFIED: JobSpec.VolumeMount.Mode
        READ_WRITE: JobSpec.VolumeMount.Mode
        READ_ONLY: JobSpec.VolumeMount.Mode
        SOURCE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_PATH_FIELD_NUMBER: _ClassVar[int]
        CONTAINER_PATH_FIELD_NUMBER: _ClassVar[int]
        MODE_FIELD_NUMBER: _ClassVar[int]
        source: str
        source_path: str
        container_path: str
        mode: JobSpec.VolumeMount.Mode
        def __init__(self, source: _Optional[str] = ..., source_path: _Optional[str] = ..., container_path: _Optional[str] = ..., mode: _Optional[_Union[JobSpec.VolumeMount.Mode, str]] = ...) -> None: ...
    class DiskSpec(_message.Message):
        __slots__ = ["type", "size_bytes"]
        TYPE_FIELD_NUMBER: _ClassVar[int]
        SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
        type: _disk_pb2.DiskSpec.DiskType
        size_bytes: int
        def __init__(self, type: _Optional[_Union[_disk_pb2.DiskSpec.DiskType, str]] = ..., size_bytes: _Optional[int] = ...) -> None: ...
    class RegistryCredentials(_message.Message):
        __slots__ = ["username", "password", "mysterybox_secret_version"]
        USERNAME_FIELD_NUMBER: _ClassVar[int]
        PASSWORD_FIELD_NUMBER: _ClassVar[int]
        MYSTERYBOX_SECRET_VERSION_FIELD_NUMBER: _ClassVar[int]
        username: str
        password: str
        mysterybox_secret_version: str
        def __init__(self, username: _Optional[str] = ..., password: _Optional[str] = ..., mysterybox_secret_version: _Optional[str] = ...) -> None: ...
    IMAGE_FIELD_NUMBER: _ClassVar[int]
    ENVIRONMENT_VARIABLES_FIELD_NUMBER: _ClassVar[int]
    PORTS_FIELD_NUMBER: _ClassVar[int]
    CONTAINER_COMMAND_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    WORKING_DIR_FIELD_NUMBER: _ClassVar[int]
    VOLUMES_FIELD_NUMBER: _ClassVar[int]
    REGISTRY_CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    PRESET_FIELD_NUMBER: _ClassVar[int]
    SHM_SIZE_BYTES_FIELD_NUMBER: _ClassVar[int]
    DISK_FIELD_NUMBER: _ClassVar[int]
    SUBNET_ID_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_IP_FIELD_NUMBER: _ClassVar[int]
    SSH_AUTHORIZED_KEYS_FIELD_NUMBER: _ClassVar[int]
    RESTART_ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    image: str
    environment_variables: _containers.RepeatedCompositeFieldContainer[JobSpec.EnvironmentVariable]
    ports: _containers.RepeatedCompositeFieldContainer[JobSpec.Port]
    container_command: str
    args: str
    working_dir: str
    volumes: _containers.RepeatedCompositeFieldContainer[JobSpec.VolumeMount]
    registry_credentials: JobSpec.RegistryCredentials
    platform: str
    preset: str
    shm_size_bytes: int
    disk: JobSpec.DiskSpec
    subnet_id: str
    public_ip: bool
    ssh_authorized_keys: _containers.RepeatedScalarFieldContainer[str]
    restart_attempts: int
    timeout: _duration_pb2.Duration
    def __init__(self, image: _Optional[str] = ..., environment_variables: _Optional[_Iterable[_Union[JobSpec.EnvironmentVariable, _Mapping]]] = ..., ports: _Optional[_Iterable[_Union[JobSpec.Port, _Mapping]]] = ..., container_command: _Optional[str] = ..., args: _Optional[str] = ..., working_dir: _Optional[str] = ..., volumes: _Optional[_Iterable[_Union[JobSpec.VolumeMount, _Mapping]]] = ..., registry_credentials: _Optional[_Union[JobSpec.RegistryCredentials, _Mapping]] = ..., platform: _Optional[str] = ..., preset: _Optional[str] = ..., shm_size_bytes: _Optional[int] = ..., disk: _Optional[_Union[JobSpec.DiskSpec, _Mapping]] = ..., subnet_id: _Optional[str] = ..., public_ip: bool = ..., ssh_authorized_keys: _Optional[_Iterable[str]] = ..., restart_attempts: _Optional[int] = ..., timeout: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class JobStatus(_message.Message):
    __slots__ = ["private_endpoints", "public_endpoints", "instances", "state", "state_details"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[JobStatus.State]
        PROVISIONING: _ClassVar[JobStatus.State]
        STARTING: _ClassVar[JobStatus.State]
        RUNNING: _ClassVar[JobStatus.State]
        CANCELLING: _ClassVar[JobStatus.State]
        DELETING: _ClassVar[JobStatus.State]
        COMPLETED: _ClassVar[JobStatus.State]
        FAILED: _ClassVar[JobStatus.State]
        CANCELLED: _ClassVar[JobStatus.State]
        ERROR: _ClassVar[JobStatus.State]
    STATE_UNSPECIFIED: JobStatus.State
    PROVISIONING: JobStatus.State
    STARTING: JobStatus.State
    RUNNING: JobStatus.State
    CANCELLING: JobStatus.State
    DELETING: JobStatus.State
    COMPLETED: JobStatus.State
    FAILED: JobStatus.State
    CANCELLED: JobStatus.State
    ERROR: JobStatus.State
    PRIVATE_ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATE_DETAILS_FIELD_NUMBER: _ClassVar[int]
    private_endpoints: _containers.RepeatedScalarFieldContainer[str]
    public_endpoints: _containers.RepeatedScalarFieldContainer[str]
    instances: _containers.RepeatedCompositeFieldContainer[JobInstanceStatus]
    state: JobStatus.State
    state_details: JobStateDetails
    def __init__(self, private_endpoints: _Optional[_Iterable[str]] = ..., public_endpoints: _Optional[_Iterable[str]] = ..., instances: _Optional[_Iterable[_Union[JobInstanceStatus, _Mapping]]] = ..., state: _Optional[_Union[JobStatus.State, str]] = ..., state_details: _Optional[_Union[JobStateDetails, _Mapping]] = ...) -> None: ...

class JobStateDetails(_message.Message):
    __slots__ = ["code", "message"]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class JobInstanceStatus(_message.Message):
    __slots__ = ["state", "compute_instance_id", "compute_instance_state", "private_ip", "public_ip"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[JobInstanceStatus.State]
        PROVISIONING: _ClassVar[JobInstanceStatus.State]
        STARTING: _ClassVar[JobInstanceStatus.State]
        RUNNING: _ClassVar[JobInstanceStatus.State]
        COMPLETING: _ClassVar[JobInstanceStatus.State]
        CANCELLING: _ClassVar[JobInstanceStatus.State]
        DELETING: _ClassVar[JobInstanceStatus.State]
        COMPLETED: _ClassVar[JobInstanceStatus.State]
        FAILED: _ClassVar[JobInstanceStatus.State]
        CANCELLED: _ClassVar[JobInstanceStatus.State]
        ERROR: _ClassVar[JobInstanceStatus.State]
    STATE_UNSPECIFIED: JobInstanceStatus.State
    PROVISIONING: JobInstanceStatus.State
    STARTING: JobInstanceStatus.State
    RUNNING: JobInstanceStatus.State
    COMPLETING: JobInstanceStatus.State
    CANCELLING: JobInstanceStatus.State
    DELETING: JobInstanceStatus.State
    COMPLETED: JobInstanceStatus.State
    FAILED: JobInstanceStatus.State
    CANCELLED: JobInstanceStatus.State
    ERROR: JobInstanceStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_INSTANCE_STATE_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_IP_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_IP_FIELD_NUMBER: _ClassVar[int]
    state: JobInstanceStatus.State
    compute_instance_id: str
    compute_instance_state: _instance_pb2.InstanceStatus.InstanceState
    private_ip: str
    public_ip: str
    def __init__(self, state: _Optional[_Union[JobInstanceStatus.State, str]] = ..., compute_instance_id: _Optional[str] = ..., compute_instance_state: _Optional[_Union[_instance_pb2.InstanceStatus.InstanceState, str]] = ..., private_ip: _Optional[str] = ..., public_ip: _Optional[str] = ...) -> None: ...
