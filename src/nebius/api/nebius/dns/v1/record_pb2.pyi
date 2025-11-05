from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Record(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: RecordSpec
    status: RecordStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[RecordSpec, _Mapping]] = ..., status: _Optional[_Union[RecordStatus, _Mapping]] = ...) -> None: ...

class RecordSpec(_message.Message):
    __slots__ = ["relative_name", "type", "ttl", "data", "deletion_protection"]
    class RecordType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        RECORD_TYPE_UNSPECIFIED: _ClassVar[RecordSpec.RecordType]
        A: _ClassVar[RecordSpec.RecordType]
        AAAA: _ClassVar[RecordSpec.RecordType]
        PTR: _ClassVar[RecordSpec.RecordType]
        CNAME: _ClassVar[RecordSpec.RecordType]
        MX: _ClassVar[RecordSpec.RecordType]
        TXT: _ClassVar[RecordSpec.RecordType]
        SRV: _ClassVar[RecordSpec.RecordType]
        NS: _ClassVar[RecordSpec.RecordType]
        SOA: _ClassVar[RecordSpec.RecordType]
        CAA: _ClassVar[RecordSpec.RecordType]
        SVCB: _ClassVar[RecordSpec.RecordType]
        HTTPS: _ClassVar[RecordSpec.RecordType]
    RECORD_TYPE_UNSPECIFIED: RecordSpec.RecordType
    A: RecordSpec.RecordType
    AAAA: RecordSpec.RecordType
    PTR: RecordSpec.RecordType
    CNAME: RecordSpec.RecordType
    MX: RecordSpec.RecordType
    TXT: RecordSpec.RecordType
    SRV: RecordSpec.RecordType
    NS: RecordSpec.RecordType
    SOA: RecordSpec.RecordType
    CAA: RecordSpec.RecordType
    SVCB: RecordSpec.RecordType
    HTTPS: RecordSpec.RecordType
    RELATIVE_NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TTL_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    DELETION_PROTECTION_FIELD_NUMBER: _ClassVar[int]
    relative_name: str
    type: RecordSpec.RecordType
    ttl: int
    data: str
    deletion_protection: bool
    def __init__(self, relative_name: _Optional[str] = ..., type: _Optional[_Union[RecordSpec.RecordType, str]] = ..., ttl: _Optional[int] = ..., data: _Optional[str] = ..., deletion_protection: bool = ...) -> None: ...

class RecordStatus(_message.Message):
    __slots__ = ["zone_domain_name", "effective_fqdn", "reconciling"]
    ZONE_DOMAIN_NAME_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_FQDN_FIELD_NUMBER: _ClassVar[int]
    RECONCILING_FIELD_NUMBER: _ClassVar[int]
    zone_domain_name: str
    effective_fqdn: str
    reconciling: bool
    def __init__(self, zone_domain_name: _Optional[str] = ..., effective_fqdn: _Optional[str] = ..., reconciling: bool = ...) -> None: ...

class GetRecordRequest(_message.Message):
    __slots__ = ["id", "resource_version"]
    ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    resource_version: int
    def __init__(self, id: _Optional[str] = ..., resource_version: _Optional[int] = ...) -> None: ...

class ListRecordsRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListRecordsResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Record]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[Record, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
