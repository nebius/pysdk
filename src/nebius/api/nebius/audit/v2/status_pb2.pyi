from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    RESPONSE_STATUS_UNSPECIFIED: _ClassVar[Status]
    STARTED: _ClassVar[Status]
    DONE: _ClassVar[Status]
    ERROR: _ClassVar[Status]
RESPONSE_STATUS_UNSPECIFIED: Status
STARTED: Status
DONE: Status
ERROR: Status
