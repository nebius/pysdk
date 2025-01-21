from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.vpc.v1alpha1 import pool_pb2 as _pool_pb2
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
    __slots__ = ["network_id", "pools", "enable_egress_nat"]
    NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    POOLS_FIELD_NUMBER: _ClassVar[int]
    ENABLE_EGRESS_NAT_FIELD_NUMBER: _ClassVar[int]
    network_id: str
    pools: _containers.RepeatedCompositeFieldContainer[SubnetPool]
    enable_egress_nat: bool
    def __init__(self, network_id: _Optional[str] = ..., pools: _Optional[_Iterable[_Union[SubnetPool, _Mapping]]] = ..., enable_egress_nat: bool = ...) -> None: ...

class SubnetPool(_message.Message):
    __slots__ = ["spec", "pool_id"]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    POOL_ID_FIELD_NUMBER: _ClassVar[int]
    spec: SubnetPoolSpec
    pool_id: str
    def __init__(self, spec: _Optional[_Union[SubnetPoolSpec, _Mapping]] = ..., pool_id: _Optional[str] = ...) -> None: ...

class SubnetPoolSpec(_message.Message):
    __slots__ = ["version", "cidrs"]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    CIDRS_FIELD_NUMBER: _ClassVar[int]
    version: _pool_pb2.IpVersion
    cidrs: _containers.RepeatedCompositeFieldContainer[SubnetCidr]
    def __init__(self, version: _Optional[_Union[_pool_pb2.IpVersion, str]] = ..., cidrs: _Optional[_Iterable[_Union[SubnetCidr, _Mapping]]] = ...) -> None: ...

class SubnetCidr(_message.Message):
    __slots__ = ["cidr", "state", "allowed_mask"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_MASK_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    state: _pool_pb2.PoolCidrState
    allowed_mask: int
    def __init__(self, cidr: _Optional[str] = ..., state: _Optional[_Union[_pool_pb2.PoolCidrState, str]] = ..., allowed_mask: _Optional[int] = ...) -> None: ...

class SubnetStatus(_message.Message):
    __slots__ = ["state", "ipv4_cidrs"]
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
    IPV4_CIDRS_FIELD_NUMBER: _ClassVar[int]
    state: SubnetStatus.State
    ipv4_cidrs: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, state: _Optional[_Union[SubnetStatus.State, str]] = ..., ipv4_cidrs: _Optional[_Iterable[str]] = ...) -> None: ...
