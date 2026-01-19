from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RouteTable(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: RouteTableSpec
    status: RouteTableStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[RouteTableSpec, _Mapping]] = ..., status: _Optional[_Union[RouteTableStatus, _Mapping]] = ...) -> None: ...

class RouteTableSpec(_message.Message):
    __slots__ = ["network_id"]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    network_id: str
    def __init__(self, network_id: _Optional[str] = ...) -> None: ...

class RouteTableStatus(_message.Message):
    __slots__ = ["state", "default", "assignment"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[RouteTableStatus.State]
        READY: _ClassVar[RouteTableStatus.State]
    STATE_UNSPECIFIED: RouteTableStatus.State
    READY: RouteTableStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_FIELD_NUMBER: _ClassVar[int]
    ASSIGNMENT_FIELD_NUMBER: _ClassVar[int]
    state: RouteTableStatus.State
    default: bool
    assignment: RouteTableAssignment
    def __init__(self, state: _Optional[_Union[RouteTableStatus.State, str]] = ..., default: bool = ..., assignment: _Optional[_Union[RouteTableAssignment, _Mapping]] = ...) -> None: ...

class RouteTableAssignment(_message.Message):
    __slots__ = ["subnets"]
    SUBNETS_FIELD_NUMBER: _ClassVar[int]
    subnets: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, subnets: _Optional[_Iterable[str]] = ...) -> None: ...
