from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class KeyState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    KEY_STATE_UNSPECIFIED: _ClassVar[KeyState]
    ACTIVE: _ClassVar[KeyState]
    SCHEDULED_FOR_DELETION: _ClassVar[KeyState]
KEY_STATE_UNSPECIFIED: KeyState
ACTIVE: KeyState
SCHEDULED_FOR_DELETION: KeyState
