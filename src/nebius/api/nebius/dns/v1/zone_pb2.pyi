from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Zone(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: ZoneSpec
    status: ZoneStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[ZoneSpec, _Mapping]] = ..., status: _Optional[_Union[ZoneStatus, _Mapping]] = ...) -> None: ...

class ZoneSpec(_message.Message):
    __slots__ = ["domain_name", "vpc", "soa_spec"]
    DOMAIN_NAME_FIELD_NUMBER: _ClassVar[int]
    VPC_FIELD_NUMBER: _ClassVar[int]
    SOA_SPEC_FIELD_NUMBER: _ClassVar[int]
    domain_name: str
    vpc: VpcZoneScope
    soa_spec: SoaSpec
    def __init__(self, domain_name: _Optional[str] = ..., vpc: _Optional[_Union[VpcZoneScope, _Mapping]] = ..., soa_spec: _Optional[_Union[SoaSpec, _Mapping]] = ...) -> None: ...

class VpcZoneScope(_message.Message):
    __slots__ = ["primary_network_id"]
    PRIMARY_NETWORK_ID_FIELD_NUMBER: _ClassVar[int]
    primary_network_id: str
    def __init__(self, primary_network_id: _Optional[str] = ...) -> None: ...

class SoaSpec(_message.Message):
    __slots__ = ["negative_ttl"]
    NEGATIVE_TTL_FIELD_NUMBER: _ClassVar[int]
    negative_ttl: int
    def __init__(self, negative_ttl: _Optional[int] = ...) -> None: ...

class ZoneStatus(_message.Message):
    __slots__ = ["record_count", "reconciling"]
    RECORD_COUNT_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    record_count: int
    reconciling: bool
    def __init__(self, record_count: _Optional[int] = ..., reconciling: bool = ...) -> None: ...

class GetZoneRequest(_message.Message):
    __slots__ = ["id", "resource_version"]
    ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    resource_version: int
    def __init__(self, id: _Optional[str] = ..., resource_version: _Optional[int] = ...) -> None: ...

class ListZonesRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListZonesResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Zone]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[Zone, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
