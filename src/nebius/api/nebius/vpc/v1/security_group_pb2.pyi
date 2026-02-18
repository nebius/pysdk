from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SecurityGroup(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: SecurityGroupSpec
    status: SecurityGroupStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[SecurityGroupSpec, _Mapping]] = ..., status: _Optional[_Union[SecurityGroupStatus, _Mapping]] = ...) -> None: ...

class SecurityGroupSpec(_message.Message):
    __slots__ = ["network_id"]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    network_id: str
    def __init__(self, network_id: _Optional[str] = ...) -> None: ...

class SecurityGroupStatus(_message.Message):
    __slots__ = ["state", "default"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[SecurityGroupStatus.State]
        READY: _ClassVar[SecurityGroupStatus.State]
    STATE_UNSPECIFIED: SecurityGroupStatus.State
    READY: SecurityGroupStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_FIELD_NUMBER: _ClassVar[int]
    state: SecurityGroupStatus.State
    default: bool
    def __init__(self, state: _Optional[_Union[SecurityGroupStatus.State, str]] = ..., default: bool = ...) -> None: ...
