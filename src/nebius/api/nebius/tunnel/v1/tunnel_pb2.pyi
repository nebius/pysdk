from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Tunnel(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: TunnelSpec
    status: TunnelStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[TunnelSpec, _Mapping]] = ..., status: _Optional[_Union[TunnelStatus, _Mapping]] = ...) -> None: ...

class TunnelSpec(_message.Message):
    __slots__ = ["title", "description"]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    title: str
    description: str
    def __init__(self, title: _Optional[str] = ..., description: _Optional[str] = ...) -> None: ...

class TunnelStatus(_message.Message):
    __slots__ = ["state"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[TunnelStatus.State]
        CREATED: _ClassVar[TunnelStatus.State]
        DELETED: _ClassVar[TunnelStatus.State]
    UNSPECIFIED: TunnelStatus.State
    CREATED: TunnelStatus.State
    DELETED: TunnelStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    state: TunnelStatus.State
    def __init__(self, state: _Optional[_Union[TunnelStatus.State, str]] = ...) -> None: ...
