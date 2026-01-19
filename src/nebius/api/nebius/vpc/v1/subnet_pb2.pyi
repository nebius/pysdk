from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.vpc.v1 import pool_pb2 as _pool_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Subnet(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: SubnetSpec
    status: SubnetStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[SubnetSpec, _Mapping]] = ..., status: _Optional[_Union[SubnetStatus, _Mapping]] = ...) -> None: ...

class SubnetSpec(_message.Message):
    __slots__ = ["network_id", "ipv4_private_pools", "ipv4_public_pools", "route_table_id"]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    IPV4_PRIVATE_POOLS_FIELD_NUMBER: _ClassVar[int]
    IPV4_PUBLIC_POOLS_FIELD_NUMBER: _ClassVar[int]
    ROUTE_TABLE_ID_FIELD_NUMBER: _ClassVar[int]
    network_id: str
    ipv4_private_pools: IPv4PrivateSubnetPools
    ipv4_public_pools: IPv4PublicSubnetPools
    route_table_id: str
    def __init__(self, network_id: _Optional[str] = ..., ipv4_private_pools: _Optional[_Union[IPv4PrivateSubnetPools, _Mapping]] = ..., ipv4_public_pools: _Optional[_Union[IPv4PublicSubnetPools, _Mapping]] = ..., route_table_id: _Optional[str] = ...) -> None: ...

class IPv4PrivateSubnetPools(_message.Message):
    __slots__ = ["pools", "use_network_pools"]
    POOLS_FIELD_NUMBER: _ClassVar[int]
    USE_NETWORK_POOLS_FIELD_NUMBER: _ClassVar[int]
    pools: _containers.RepeatedCompositeFieldContainer[SubnetPool]
    use_network_pools: bool
    def __init__(self, pools: _Optional[_Iterable[_Union[SubnetPool, _Mapping]]] = ..., use_network_pools: bool = ...) -> None: ...

class IPv4PublicSubnetPools(_message.Message):
    __slots__ = ["pools", "use_network_pools"]
    POOLS_FIELD_NUMBER: _ClassVar[int]
    USE_NETWORK_POOLS_FIELD_NUMBER: _ClassVar[int]
    pools: _containers.RepeatedCompositeFieldContainer[SubnetPool]
    use_network_pools: bool
    def __init__(self, pools: _Optional[_Iterable[_Union[SubnetPool, _Mapping]]] = ..., use_network_pools: bool = ...) -> None: ...

class SubnetPool(_message.Message):
    __slots__ = ["cidrs"]
    CIDRS_FIELD_NUMBER: _ClassVar[int]
    cidrs: _containers.RepeatedCompositeFieldContainer[SubnetCidr]
    def __init__(self, cidrs: _Optional[_Iterable[_Union[SubnetCidr, _Mapping]]] = ...) -> None: ...

class SubnetCidr(_message.Message):
    __slots__ = ["cidr", "state", "max_mask_length"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    MAX_MASK_LENGTH_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    state: _pool_pb2.AddressBlockState
    max_mask_length: int
    def __init__(self, cidr: _Optional[str] = ..., state: _Optional[_Union[_pool_pb2.AddressBlockState, str]] = ..., max_mask_length: _Optional[int] = ...) -> None: ...

class SubnetStatus(_message.Message):
    __slots__ = ["state", "ipv4_private_cidrs", "ipv4_public_cidrs", "route_table"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[SubnetStatus.State]
        CREATING: _ClassVar[SubnetStatus.State]
        READY: _ClassVar[SubnetStatus.State]
        DELETING: _ClassVar[SubnetStatus.State]
    STATE_UNSPECIFIED: SubnetStatus.State
    CREATING: SubnetStatus.State
    READY: SubnetStatus.State
    DELETING: SubnetStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    IPV4_PRIVATE_CIDRS_FIELD_NUMBER: _ClassVar[int]
    IPV4_PUBLIC_CIDRS_FIELD_NUMBER: _ClassVar[int]
    ROUTE_TABLE_FIELD_NUMBER: _ClassVar[int]
    state: SubnetStatus.State
    ipv4_private_cidrs: _containers.RepeatedScalarFieldContainer[str]
    ipv4_public_cidrs: _containers.RepeatedScalarFieldContainer[str]
    route_table: SubnetAssociatedRouteTable
    def __init__(self, state: _Optional[_Union[SubnetStatus.State, str]] = ..., ipv4_private_cidrs: _Optional[_Iterable[str]] = ..., ipv4_public_cidrs: _Optional[_Iterable[str]] = ..., route_table: _Optional[_Union[SubnetAssociatedRouteTable, _Mapping]] = ...) -> None: ...

class SubnetAssociatedRouteTable(_message.Message):
    __slots__ = ["id", "default"]
    ID_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_FIELD_NUMBER: _ClassVar[int]
    id: str
    default: bool
    def __init__(self, id: _Optional[str] = ..., default: bool = ...) -> None: ...
