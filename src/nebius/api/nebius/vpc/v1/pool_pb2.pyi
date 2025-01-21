from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AddressBlockState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    STATE_UNSPECIFIED: _ClassVar[AddressBlockState]
    AVAILABLE: _ClassVar[AddressBlockState]
    DISABLED: _ClassVar[AddressBlockState]

class IpVersion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    IP_VERSION_UNSPECIFIED: _ClassVar[IpVersion]
    IPV4: _ClassVar[IpVersion]
    IPV6: _ClassVar[IpVersion]

class IpVisibility(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    IP_VISIBILITY_UNSPECIFIED: _ClassVar[IpVisibility]
    PRIVATE: _ClassVar[IpVisibility]
    PUBLIC: _ClassVar[IpVisibility]
STATE_UNSPECIFIED: AddressBlockState
AVAILABLE: AddressBlockState
DISABLED: AddressBlockState
IP_VERSION_UNSPECIFIED: IpVersion
IPV4: IpVersion
IPV6: IpVersion
IP_VISIBILITY_UNSPECIFIED: IpVisibility
PRIVATE: IpVisibility
PUBLIC: IpVisibility

class Pool(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: PoolSpec
    status: PoolStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[PoolSpec, _Mapping]] = ..., status: _Optional[_Union[PoolStatus, _Mapping]] = ...) -> None: ...

class PoolSpec(_message.Message):
    __slots__ = ["source_pool_id", "version", "visibility", "cidrs"]
    SOURCE_POOL_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    VISIBILITY_FIELD_NUMBER: _ClassVar[int]
    CIDRS_FIELD_NUMBER: _ClassVar[int]
    source_pool_id: str
    version: IpVersion
    visibility: IpVisibility
    cidrs: _containers.RepeatedCompositeFieldContainer[PoolCidr]
    def __init__(self, source_pool_id: _Optional[str] = ..., version: _Optional[_Union[IpVersion, str]] = ..., visibility: _Optional[_Union[IpVisibility, str]] = ..., cidrs: _Optional[_Iterable[_Union[PoolCidr, _Mapping]]] = ...) -> None: ...

class PoolCidr(_message.Message):
    __slots__ = ["cidr", "state", "max_mask_length"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    MAX_MASK_LENGTH_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    state: AddressBlockState
    max_mask_length: int
    def __init__(self, cidr: _Optional[str] = ..., state: _Optional[_Union[AddressBlockState, str]] = ..., max_mask_length: _Optional[int] = ...) -> None: ...

class PoolStatus(_message.Message):
    __slots__ = ["state", "cidrs", "scope_id", "assignment"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[PoolStatus.State]
        CREATING: _ClassVar[PoolStatus.State]
        READY: _ClassVar[PoolStatus.State]
        DELETING: _ClassVar[PoolStatus.State]
    STATE_UNSPECIFIED: PoolStatus.State
    CREATING: PoolStatus.State
    READY: PoolStatus.State
    DELETING: PoolStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    CIDRS_FIELD_NUMBER: _ClassVar[int]
    SCOPE_ID_FIELD_NUMBER: _ClassVar[int]
    ASSIGNMENT_FIELD_NUMBER: _ClassVar[int]
    state: PoolStatus.State
    cidrs: _containers.RepeatedScalarFieldContainer[str]
    scope_id: str
    assignment: PoolAssignment
    def __init__(self, state: _Optional[_Union[PoolStatus.State, str]] = ..., cidrs: _Optional[_Iterable[str]] = ..., scope_id: _Optional[str] = ..., assignment: _Optional[_Union[PoolAssignment, _Mapping]] = ...) -> None: ...

class PoolAssignment(_message.Message):
    __slots__ = ["networks", "subnets"]
    NETWORKS_FIELD_NUMBER: _ClassVar[int]
    SUBNETS_FIELD_NUMBER: _ClassVar[int]
    networks: _containers.RepeatedScalarFieldContainer[str]
    subnets: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, networks: _Optional[_Iterable[str]] = ..., subnets: _Optional[_Iterable[str]] = ...) -> None: ...
