from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ClusterStatus(_message.Message):
    __slots__ = ["phase", "state", "reconciling"]
    class Phase(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        PHASE_UNSPECIFIED: _ClassVar[ClusterStatus.Phase]
        PHASE_PROVISIONING: _ClassVar[ClusterStatus.Phase]
        PHASE_RUNNING: _ClassVar[ClusterStatus.Phase]
        PHASE_UPDATING: _ClassVar[ClusterStatus.Phase]
        PHASE_DELETING: _ClassVar[ClusterStatus.Phase]
        PHASE_DELETED: _ClassVar[ClusterStatus.Phase]
        PHASE_PURGING: _ClassVar[ClusterStatus.Phase]
        PHASE_STOPPING: _ClassVar[ClusterStatus.Phase]
        PHASE_RESUMING: _ClassVar[ClusterStatus.Phase]
    PHASE_UNSPECIFIED: ClusterStatus.Phase
    PHASE_PROVISIONING: ClusterStatus.Phase
    PHASE_RUNNING: ClusterStatus.Phase
    PHASE_UPDATING: ClusterStatus.Phase
    PHASE_DELETING: ClusterStatus.Phase
    PHASE_DELETED: ClusterStatus.Phase
    PHASE_PURGING: ClusterStatus.Phase
    PHASE_STOPPING: ClusterStatus.Phase
    PHASE_RESUMING: ClusterStatus.Phase
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[ClusterStatus.State]
        STATE_IN_PROGRESS: _ClassVar[ClusterStatus.State]
        STATE_FINISHED: _ClassVar[ClusterStatus.State]
        STATE_ERROR: _ClassVar[ClusterStatus.State]
        STATE_DEGRADED: _ClassVar[ClusterStatus.State]
        STATE_SCHEDULED: _ClassVar[ClusterStatus.State]
    STATE_UNSPECIFIED: ClusterStatus.State
    STATE_IN_PROGRESS: ClusterStatus.State
    STATE_FINISHED: ClusterStatus.State
    STATE_ERROR: ClusterStatus.State
    STATE_DEGRADED: ClusterStatus.State
    STATE_SCHEDULED: ClusterStatus.State
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    phase: ClusterStatus.Phase
    state: ClusterStatus.State
    reconciling: bool
    def __init__(self, phase: _Optional[_Union[ClusterStatus.Phase, str]] = ..., state: _Optional[_Union[ClusterStatus.State, str]] = ..., reconciling: bool = ...) -> None: ...
