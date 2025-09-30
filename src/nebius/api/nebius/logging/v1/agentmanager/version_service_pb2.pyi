from google.protobuf import duration_pb2 as _duration_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AgentType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    AGENT_UNDEFINED: _ClassVar[AgentType]
    O11Y_AGENT: _ClassVar[AgentType]

class AgentState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    STATE_UNDEFINED: _ClassVar[AgentState]
    STATE_HEALTHY: _ClassVar[AgentState]
    STATE_ERROR: _ClassVar[AgentState]

class Action(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    ACTION_UNDEFINED: _ClassVar[Action]
    NOP: _ClassVar[Action]
    UPDATE: _ClassVar[Action]
    RESTART: _ClassVar[Action]
AGENT_UNDEFINED: AgentType
O11Y_AGENT: AgentType
STATE_UNDEFINED: AgentState
STATE_HEALTHY: AgentState
STATE_ERROR: AgentState
ACTION_UNDEFINED: Action
NOP: Action
UPDATE: Action
RESTART: Action

class GetVersionRequest(_message.Message):
    __slots__ = ["type", "agent_version", "updater_version", "parent_id", "instance_id", "os_info", "agent_state", "agent_uptime", "system_uptime", "updater_uptime", "agent_state_messages", "last_update_error", "mk8s_cluster_id", "modules_health", "cloud_init_status", "instance_id_used_fallback", "last_agent_logs", "gpu_model", "gpu_number", "dcgm_version"]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    AGENT_VERSION_FIELD_NUMBER: _ClassVar[int]
    UPDATER_VERSION_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    OS_INFO_FIELD_NUMBER: _ClassVar[int]
    AGENT_STATE_FIELD_NUMBER: _ClassVar[int]
    AGENT_UPTIME_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_UPTIME_FIELD_NUMBER: _ClassVar[int]
    UPDATER_UPTIME_FIELD_NUMBER: _ClassVar[int]
    AGENT_STATE_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    LAST_UPDATE_ERROR_FIELD_NUMBER: _ClassVar[int]
    MK8S_CLUSTER_ID_FIELD_NUMBER: _ClassVar[int]
    MODULES_HEALTH_FIELD_NUMBER: _ClassVar[int]
    CLOUD_INIT_STATUS_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_ID_USED_FALLBACK_FIELD_NUMBER: _ClassVar[int]
    LAST_AGENT_LOGS_FIELD_NUMBER: _ClassVar[int]
    GPU_MODEL_FIELD_NUMBER: _ClassVar[int]
    GPU_NUMBER_FIELD_NUMBER: _ClassVar[int]
    DCGM_VERSION_FIELD_NUMBER: _ClassVar[int]
    type: AgentType
    agent_version: str
    updater_version: str
    parent_id: str
    instance_id: str
    os_info: OSInfo
    agent_state: AgentState
    agent_uptime: _duration_pb2.Duration
    system_uptime: _duration_pb2.Duration
    updater_uptime: _duration_pb2.Duration
    agent_state_messages: _containers.RepeatedScalarFieldContainer[str]
    last_update_error: str
    mk8s_cluster_id: str
    modules_health: ModulesHealth
    cloud_init_status: str
    instance_id_used_fallback: bool
    last_agent_logs: str
    gpu_model: str
    gpu_number: int
    dcgm_version: str
    def __init__(self, type: _Optional[_Union[AgentType, str]] = ..., agent_version: _Optional[str] = ..., updater_version: _Optional[str] = ..., parent_id: _Optional[str] = ..., instance_id: _Optional[str] = ..., os_info: _Optional[_Union[OSInfo, _Mapping]] = ..., agent_state: _Optional[_Union[AgentState, str]] = ..., agent_uptime: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., system_uptime: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., updater_uptime: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., agent_state_messages: _Optional[_Iterable[str]] = ..., last_update_error: _Optional[str] = ..., mk8s_cluster_id: _Optional[str] = ..., modules_health: _Optional[_Union[ModulesHealth, _Mapping]] = ..., cloud_init_status: _Optional[str] = ..., instance_id_used_fallback: bool = ..., last_agent_logs: _Optional[str] = ..., gpu_model: _Optional[str] = ..., gpu_number: _Optional[int] = ..., dcgm_version: _Optional[str] = ...) -> None: ...

class ModulesHealth(_message.Message):
    __slots__ = ["process", "gpu_pipeline", "cpu_pipeline", "cilium_pipeline", "vmapps_pipeline"]
    PROCESS_FIELD_NUMBER: _ClassVar[int]
    GPU_PIPELINE_FIELD_NUMBER: _ClassVar[int]
    CPU_PIPELINE_FIELD_NUMBER: _ClassVar[int]
    CILIUM_PIPELINE_FIELD_NUMBER: _ClassVar[int]
    VMAPPS_PIPELINE_FIELD_NUMBER: _ClassVar[int]
    process: ModuleHealth
    gpu_pipeline: ModuleHealth
    cpu_pipeline: ModuleHealth
    cilium_pipeline: ModuleHealth
    vmapps_pipeline: ModuleHealth
    def __init__(self, process: _Optional[_Union[ModuleHealth, _Mapping]] = ..., gpu_pipeline: _Optional[_Union[ModuleHealth, _Mapping]] = ..., cpu_pipeline: _Optional[_Union[ModuleHealth, _Mapping]] = ..., cilium_pipeline: _Optional[_Union[ModuleHealth, _Mapping]] = ..., vmapps_pipeline: _Optional[_Union[ModuleHealth, _Mapping]] = ...) -> None: ...

class ModuleHealth(_message.Message):
    __slots__ = ["state", "messages", "parameters"]
    STATE_FIELD_NUMBER: _ClassVar[int]
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    state: AgentState
    messages: _containers.RepeatedScalarFieldContainer[str]
    parameters: _containers.RepeatedCompositeFieldContainer[Parameter]
    def __init__(self, state: _Optional[_Union[AgentState, str]] = ..., messages: _Optional[_Iterable[str]] = ..., parameters: _Optional[_Iterable[_Union[Parameter, _Mapping]]] = ...) -> None: ...

class Parameter(_message.Message):
    __slots__ = ["name", "value"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    name: str
    value: str
    def __init__(self, name: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...

class OSInfo(_message.Message):
    __slots__ = ["name", "uname", "architecture"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    UNAME_FIELD_NUMBER: _ClassVar[int]
    ARCHITECTURE_FIELD_NUMBER: _ClassVar[int]
    name: str
    uname: str
    architecture: str
    def __init__(self, name: _Optional[str] = ..., uname: _Optional[str] = ..., architecture: _Optional[str] = ...) -> None: ...

class GetVersionResponse(_message.Message):
    __slots__ = ["action", "nop", "update", "restart"]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    NOP_FIELD_NUMBER: _ClassVar[int]
    UPDATE_FIELD_NUMBER: _ClassVar[int]
    RESTART_FIELD_NUMBER: _ClassVar[int]
    action: Action
    nop: NopActionParams
    update: UpdateActionParams
    restart: RestartActionParams
    def __init__(self, action: _Optional[_Union[Action, str]] = ..., nop: _Optional[_Union[NopActionParams, _Mapping]] = ..., update: _Optional[_Union[UpdateActionParams, _Mapping]] = ..., restart: _Optional[_Union[RestartActionParams, _Mapping]] = ...) -> None: ...

class NopActionParams(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class UpdateActionParams(_message.Message):
    __slots__ = ["version", "repo_url"]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    REPO_URL_FIELD_NUMBER: _ClassVar[int]
    version: str
    repo_url: str
    def __init__(self, version: _Optional[str] = ..., repo_url: _Optional[str] = ...) -> None: ...

class RestartActionParams(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
