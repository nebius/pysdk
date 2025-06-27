from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.iam.v2 import tenant_pb2 as _tenant_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetTenantRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetTenantByNameRequest(_message.Message):
    __slots__ = ["parent_id", "name"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    name: str
    def __init__(self, parent_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class UpdateTenantRequest(_message.Message):
    __slots__ = ["metadata", "spec", "name_prefix"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    NAME_PREFIX_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _tenant_pb2.TenantSpec
    name_prefix: str
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_tenant_pb2.TenantSpec, _Mapping]] = ..., name_prefix: _Optional[str] = ...) -> None: ...

class ListTenantsRequest(_message.Message):
    __slots__ = ["page_size", "page_token", "filter"]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    page_size: int
    page_token: str
    filter: str
    def __init__(self, page_size: _Optional[int] = ..., page_token: _Optional[str] = ..., filter: _Optional[str] = ...) -> None: ...

class ListTenantsResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_tenant_pb2.Tenant]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_tenant_pb2.Tenant, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
