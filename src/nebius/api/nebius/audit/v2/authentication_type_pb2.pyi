from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class AuthenticationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    AUTHENTICATION_TYPE_UNSPECIFIED: _ClassVar[AuthenticationType]
    ACCESS_TOKEN: _ClassVar[AuthenticationType]
    STATIC_KEY: _ClassVar[AuthenticationType]
AUTHENTICATION_TYPE_UNSPECIFIED: AuthenticationType
ACCESS_TOKEN: AuthenticationType
STATIC_KEY: AuthenticationType
