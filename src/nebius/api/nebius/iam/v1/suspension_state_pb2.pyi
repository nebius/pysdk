from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class SuspensionState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    SUSPENSION_STATE_UNSPECIFIED: _ClassVar[SuspensionState]
    NONE: _ClassVar[SuspensionState]
    SUSPENDING: _ClassVar[SuspensionState]
    SUSPENDED: _ClassVar[SuspensionState]
    RESUMING: _ClassVar[SuspensionState]
SUSPENSION_STATE_UNSPECIFIED: SuspensionState
NONE: SuspensionState
SUSPENDING: SuspensionState
SUSPENDED: SuspensionState
RESUMING: SuspensionState
