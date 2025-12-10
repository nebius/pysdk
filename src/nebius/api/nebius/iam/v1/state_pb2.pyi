from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    STATE_UNSPECIFIED: _ClassVar[State]
    ACTIVE: _ClassVar[State]
    SCHEDULING_FOR_DELETION: _ClassVar[State]
    SCHEDULED_FOR_DELETION: _ClassVar[State]
    SCHEDULING_FOR_DELETION_BY_PARENT: _ClassVar[State]
    SCHEDULED_FOR_DELETION_BY_PARENT: _ClassVar[State]
    UNDELETING: _ClassVar[State]
    PURGING: _ClassVar[State]
    PURGED: _ClassVar[State]
    CREATED: _ClassVar[State]
    ACTIVATING: _ClassVar[State]
    PARKING: _ClassVar[State]
    PARKED: _ClassVar[State]
    CREATING: _ClassVar[State]
STATE_UNSPECIFIED: State
ACTIVE: State
SCHEDULING_FOR_DELETION: State
SCHEDULED_FOR_DELETION: State
SCHEDULING_FOR_DELETION_BY_PARENT: State
SCHEDULED_FOR_DELETION_BY_PARENT: State
UNDELETING: State
PURGING: State
PURGED: State
CREATED: State
ACTIVATING: State
PARKING: State
PARKED: State
CREATING: State
