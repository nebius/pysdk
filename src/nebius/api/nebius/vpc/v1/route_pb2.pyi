from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Route(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: RouteSpec
    status: RouteStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[RouteSpec, _Mapping]] = ..., status: _Optional[_Union[RouteStatus, _Mapping]] = ...) -> None: ...

class RouteSpec(_message.Message):
    __slots__ = ["description", "destination", "next_hop"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    NEXT_HOP_FIELD_NUMBER: _ClassVar[int]
    description: str
    destination: DestinationMatch
    next_hop: NextHop
    def __init__(self, description: _Optional[str] = ..., destination: _Optional[_Union[DestinationMatch, _Mapping]] = ..., next_hop: _Optional[_Union[NextHop, _Mapping]] = ...) -> None: ...

class DestinationMatch(_message.Message):
    __slots__ = ["cidr"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    def __init__(self, cidr: _Optional[str] = ...) -> None: ...

class NextHop(_message.Message):
    __slots__ = ["allocation", "default_egress_gateway"]
    ALLOCATION_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_EGRESS_GATEWAY_FIELD_NUMBER: _ClassVar[int]
    allocation: AllocationNextHop
    default_egress_gateway: bool
    def __init__(self, allocation: _Optional[_Union[AllocationNextHop, _Mapping]] = ..., default_egress_gateway: bool = ...) -> None: ...

class AllocationNextHop(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class RouteStatus(_message.Message):
    __slots__ = ["state", "next_hop"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[RouteStatus.State]
        READY: _ClassVar[RouteStatus.State]
    STATE_UNSPECIFIED: RouteStatus.State
    READY: RouteStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    NEXT_HOP_FIELD_NUMBER: _ClassVar[int]
    state: RouteStatus.State
    next_hop: NextHopState
    def __init__(self, state: _Optional[_Union[RouteStatus.State, str]] = ..., next_hop: _Optional[_Union[NextHopState, _Mapping]] = ...) -> None: ...

class NextHopState(_message.Message):
    __slots__ = ["allocation", "default_egress_gateway"]
    ALLOCATION_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_EGRESS_GATEWAY_FIELD_NUMBER: _ClassVar[int]
    allocation: AllocationNextHopState
    default_egress_gateway: DefaultEgressGatewayState
    def __init__(self, allocation: _Optional[_Union[AllocationNextHopState, _Mapping]] = ..., default_egress_gateway: _Optional[_Union[DefaultEgressGatewayState, _Mapping]] = ...) -> None: ...

class AllocationNextHopState(_message.Message):
    __slots__ = ["cidr"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    def __init__(self, cidr: _Optional[str] = ...) -> None: ...

class DefaultEgressGatewayState(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
