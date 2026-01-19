from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PoolCidrState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    STATE_UNSPECIFIED: _ClassVar[PoolCidrState]
    AVAILABLE: _ClassVar[PoolCidrState]
    DISABLED: _ClassVar[PoolCidrState]

class IpVersion(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    IP_VERSION_UNSPECIFIED: _ClassVar[IpVersion]
    IPV4: _ClassVar[IpVersion]
    IPV6: _ClassVar[IpVersion]
STATE_UNSPECIFIED: PoolCidrState
AVAILABLE: PoolCidrState
DISABLED: PoolCidrState
IP_VERSION_UNSPECIFIED: IpVersion
IPV4: IpVersion
IPV6: IpVersion

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
    __slots__ = ["source_pool_id", "source_scope_id", "version", "cidrs"]
    SOURCE_POOL_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_SCOPE_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    CIDRS_FIELD_NUMBER: _ClassVar[int]
    source_pool_id: str
    source_scope_id: str
    version: IpVersion
    cidrs: _containers.RepeatedCompositeFieldContainer[PoolCidr]
    def __init__(self, source_pool_id: _Optional[str] = ..., source_scope_id: _Optional[str] = ..., version: _Optional[_Union[IpVersion, str]] = ..., cidrs: _Optional[_Iterable[_Union[PoolCidr, _Mapping]]] = ...) -> None: ...

class PoolCidr(_message.Message):
    __slots__ = ["cidr", "state", "allowed_mask"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_MASK_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    state: PoolCidrState
    allowed_mask: int
    def __init__(self, cidr: _Optional[str] = ..., state: _Optional[_Union[PoolCidrState, str]] = ..., allowed_mask: _Optional[int] = ...) -> None: ...

class PoolStatus(_message.Message):
    __slots__ = ["state", "cidrs", "scope_id"]
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
    state: PoolStatus.State
    cidrs: _containers.RepeatedScalarFieldContainer[str]
    scope_id: str
    def __init__(self, state: _Optional[_Union[PoolStatus.State, str]] = ..., cidrs: _Optional[_Iterable[str]] = ..., scope_id: _Optional[str] = ...) -> None: ...
