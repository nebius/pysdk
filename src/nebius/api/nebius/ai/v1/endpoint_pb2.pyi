from nebius.api.buf.validate import validate_pb2 as _validate_pb2
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
    __slots__ = ["image", "environment_variables", "ports", "container_command", "args", "working_dir", "volumes", "registry_credentials", "platform", "preset", "shm_size_bytes", "disk", "subnet_id", "public_ip", "ssh_authorized_keys", "auth_token"]
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
            PROTOCOL_UNSPECIFIED: _ClassVar[EndpointSpec.Port.Protocol]
            HTTP: _ClassVar[EndpointSpec.Port.Protocol]
            TCP: _ClassVar[EndpointSpec.Port.Protocol]
            UDP: _ClassVar[EndpointSpec.Port.Protocol]
        PROTOCOL_UNSPECIFIED: EndpointSpec.Port.Protocol
        HTTP: EndpointSpec.Port.Protocol
        TCP: EndpointSpec.Port.Protocol
        UDP: EndpointSpec.Port.Protocol
        CONTAINER_PORT_FIELD_NUMBER: _ClassVar[int]
        HOST_PORT_FIELD_NUMBER: _ClassVar[int]
        PROTOCOL_FIELD_NUMBER: _ClassVar[int]
        container_port: int
        host_port: int
        protocol: EndpointSpec.Port.Protocol
        def __init__(self, container_port: _Optional[int] = ..., host_port: _Optional[int] = ..., protocol: _Optional[_Union[EndpointSpec.Port.Protocol, str]] = ...) -> None: ...
    class VolumeMount(_message.Message):
        __slots__ = ["source", "source_path", "container_path", "mode"]
        class Mode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = []
            MODE_UNSPECIFIED: _ClassVar[EndpointSpec.VolumeMount.Mode]
            READ_ONLY: _ClassVar[EndpointSpec.VolumeMount.Mode]
            READ_WRITE: _ClassVar[EndpointSpec.VolumeMount.Mode]
        MODE_UNSPECIFIED: EndpointSpec.VolumeMount.Mode
        READ_ONLY: EndpointSpec.VolumeMount.Mode
        READ_WRITE: EndpointSpec.VolumeMount.Mode
        SOURCE_FIELD_NUMBER: _ClassVar[int]
        SOURCE_PATH_FIELD_NUMBER: _ClassVar[int]
        CONTAINER_PATH_FIELD_NUMBER: _ClassVar[int]
        MODE_FIELD_NUMBER: _ClassVar[int]
        source: str
        source_path: str
        container_path: str
        mode: EndpointSpec.VolumeMount.Mode
        def __init__(self, source: _Optional[str] = ..., source_path: _Optional[str] = ..., container_path: _Optional[str] = ..., mode: _Optional[_Union[EndpointSpec.VolumeMount.Mode, str]] = ...) -> None: ...
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
    AUTH_TOKEN_FIELD_NUMBER: _ClassVar[int]
    image: str
    environment_variables: _containers.RepeatedCompositeFieldContainer[EndpointSpec.EnvironmentVariable]
    ports: _containers.RepeatedCompositeFieldContainer[EndpointSpec.Port]
    container_command: str
    args: str
    working_dir: str
    volumes: _containers.RepeatedCompositeFieldContainer[EndpointSpec.VolumeMount]
    registry_credentials: EndpointSpec.RegistryCredentials
    platform: str
    preset: str
    shm_size_bytes: int
    disk: EndpointSpec.DiskSpec
    subnet_id: str
    public_ip: bool
    ssh_authorized_keys: _containers.RepeatedScalarFieldContainer[str]
    auth_token: str
    def __init__(self, image: _Optional[str] = ..., environment_variables: _Optional[_Iterable[_Union[EndpointSpec.EnvironmentVariable, _Mapping]]] = ..., ports: _Optional[_Iterable[_Union[EndpointSpec.Port, _Mapping]]] = ..., container_command: _Optional[str] = ..., args: _Optional[str] = ..., working_dir: _Optional[str] = ..., volumes: _Optional[_Iterable[_Union[EndpointSpec.VolumeMount, _Mapping]]] = ..., registry_credentials: _Optional[_Union[EndpointSpec.RegistryCredentials, _Mapping]] = ..., platform: _Optional[str] = ..., preset: _Optional[str] = ..., shm_size_bytes: _Optional[int] = ..., disk: _Optional[_Union[EndpointSpec.DiskSpec, _Mapping]] = ..., subnet_id: _Optional[str] = ..., public_ip: bool = ..., ssh_authorized_keys: _Optional[_Iterable[str]] = ..., auth_token: _Optional[str] = ...) -> None: ...

class EndpointStatus(_message.Message):
    __slots__ = ["private_endpoints", "public_endpoints", "instances", "state", "state_details"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[EndpointStatus.State]
        PROVISIONING: _ClassVar[EndpointStatus.State]
        STARTING: _ClassVar[EndpointStatus.State]
        RUNNING: _ClassVar[EndpointStatus.State]
        STOPPING: _ClassVar[EndpointStatus.State]
        DELETING: _ClassVar[EndpointStatus.State]
        STOPPED: _ClassVar[EndpointStatus.State]
        ERROR: _ClassVar[EndpointStatus.State]
    STATE_UNSPECIFIED: EndpointStatus.State
    PROVISIONING: EndpointStatus.State
    STARTING: EndpointStatus.State
    RUNNING: EndpointStatus.State
    STOPPING: EndpointStatus.State
    DELETING: EndpointStatus.State
    STOPPED: EndpointStatus.State
    ERROR: EndpointStatus.State
    PRIVATE_ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_ENDPOINTS_FIELD_NUMBER: _ClassVar[int]
    INSTANCES_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    STATE_DETAILS_FIELD_NUMBER: _ClassVar[int]
    private_endpoints: _containers.RepeatedScalarFieldContainer[str]
    public_endpoints: _containers.RepeatedScalarFieldContainer[str]
    instances: _containers.RepeatedCompositeFieldContainer[EndpointInstanceStatus]
    state: EndpointStatus.State
    state_details: EndpointStateDetails
    def __init__(self, private_endpoints: _Optional[_Iterable[str]] = ..., public_endpoints: _Optional[_Iterable[str]] = ..., instances: _Optional[_Iterable[_Union[EndpointInstanceStatus, _Mapping]]] = ..., state: _Optional[_Union[EndpointStatus.State, str]] = ..., state_details: _Optional[_Union[EndpointStateDetails, _Mapping]] = ...) -> None: ...

class EndpointStateDetails(_message.Message):
    __slots__ = ["code", "message"]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    code: str
    message: str
    def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class EndpointInstanceStatus(_message.Message):
    __slots__ = ["state", "compute_instance_id", "compute_instance_state", "private_ip", "public_ip"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[EndpointInstanceStatus.State]
        PROVISIONING: _ClassVar[EndpointInstanceStatus.State]
        STARTING: _ClassVar[EndpointInstanceStatus.State]
        RUNNING: _ClassVar[EndpointInstanceStatus.State]
        STOPPING: _ClassVar[EndpointInstanceStatus.State]
        DELETING: _ClassVar[EndpointInstanceStatus.State]
        STOPPED: _ClassVar[EndpointInstanceStatus.State]
        FAILED: _ClassVar[EndpointInstanceStatus.State]
        ERROR: _ClassVar[EndpointInstanceStatus.State]
    STATE_UNSPECIFIED: EndpointInstanceStatus.State
    PROVISIONING: EndpointInstanceStatus.State
    STARTING: EndpointInstanceStatus.State
    RUNNING: EndpointInstanceStatus.State
    STOPPING: EndpointInstanceStatus.State
    DELETING: EndpointInstanceStatus.State
    STOPPED: EndpointInstanceStatus.State
    FAILED: EndpointInstanceStatus.State
    ERROR: EndpointInstanceStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_INSTANCE_STATE_FIELD_NUMBER: _ClassVar[int]
    PRIVATE_IP_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_IP_FIELD_NUMBER: _ClassVar[int]
    state: EndpointInstanceStatus.State
    compute_instance_id: str
    compute_instance_state: _instance_pb2.InstanceStatus.InstanceState
    private_ip: str
    public_ip: str
    def __init__(self, state: _Optional[_Union[EndpointInstanceStatus.State, str]] = ..., compute_instance_id: _Optional[str] = ..., compute_instance_state: _Optional[_Union[_instance_pb2.InstanceStatus.InstanceState, str]] = ..., private_ip: _Optional[str] = ..., public_ip: _Optional[str] = ...) -> None: ...
