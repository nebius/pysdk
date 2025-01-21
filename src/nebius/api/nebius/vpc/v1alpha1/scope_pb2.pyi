from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Scope(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ScopeSpec
    status: ScopeStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ScopeSpec, _Mapping]] = ..., status: _Optional[_Union[ScopeStatus, _Mapping]] = ...) -> None: ...

class ScopeSpec(_message.Message):
    __slots__ = ["type"]
    class Type(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        SCOPE_TYPE_UNSPECIFIED: _ClassVar[ScopeSpec.Type]
        PUBLIC: _ClassVar[ScopeSpec.Type]
        PRIVATE: _ClassVar[ScopeSpec.Type]
    SCOPE_TYPE_UNSPECIFIED: ScopeSpec.Type
    PUBLIC: ScopeSpec.Type
    PRIVATE: ScopeSpec.Type
    TYPE_FIELD_NUMBER: _ClassVar[int]
    type: ScopeSpec.Type
    def __init__(self, type: _Optional[_Union[ScopeSpec.Type, str]] = ...) -> None: ...

class ScopeStatus(_message.Message):
    __slots__ = ["state"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[ScopeStatus.State]
        CREATING: _ClassVar[ScopeStatus.State]
        READY: _ClassVar[ScopeStatus.State]
        DELETING: _ClassVar[ScopeStatus.State]
    STATE_UNSPECIFIED: ScopeStatus.State
    CREATING: ScopeStatus.State
    READY: ScopeStatus.State
    DELETING: ScopeStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: ScopeStatus.State
    def __init__(self, state: _Optional[_Union[ScopeStatus.State, str]] = ...) -> None: ...
