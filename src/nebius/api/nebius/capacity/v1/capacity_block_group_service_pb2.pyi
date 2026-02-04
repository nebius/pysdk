from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.capacity.v1 import capacity_block_group_pb2 as _capacity_block_group_pb2
from nebius.api.nebius.capacity.v1 import resource_affinity_pb2 as _resource_affinity_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetCapacityBlockGroupRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetCapacityBlockGroupByResourceAffinityRequest(_message.Message):
    __slots__ = ["parent_id", "region", "resource_affinity"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_AFFINITY_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    region: str
    resource_affinity: _resource_affinity_pb2.ResourceAffinity
    def __init__(self, parent_id: _Optional[str] = ..., region: _Optional[str] = ..., resource_affinity: _Optional[_Union[_resource_affinity_pb2.ResourceAffinity, _Mapping]] = ...) -> None: ...

class ListCapacityBlockGroupsRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListCapacityBlockGroupsResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_capacity_block_group_pb2.CapacityBlockGroup]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_capacity_block_group_pb2.CapacityBlockGroup, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListCapacityBlockGroupResourcesRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListCapacityBlockGroupResourcesResponse(_message.Message):
    __slots__ = ["resource_ids"]
    RESOURCE_IDS_FIELD_NUMBER: _ClassVar[int]
    resource_ids: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, resource_ids: _Optional[_Iterable[str]] = ...) -> None: ...
