from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.capacity.v1 import capacity_allowance_pb2 as _capacity_allowance_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ListCapacityAllowancesRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListCapacityAllowancesResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_capacity_allowance_pb2.CapacityAllowance]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_capacity_allowance_pb2.CapacityAllowance, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ListCapacityAllowancesByCapacityBlockGroupRequest(_message.Message):
    __slots__ = ["capacity_block_group_id", "page_size", "page_token"]
    CAPACITY_BLOCK_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    capacity_block_group_id: str
    page_size: int
    page_token: str
    def __init__(self, capacity_block_group_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class GetCapacityAllowanceRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetCapacityAllowanceByParentAndCapacityBlockGroupRequest(_message.Message):
    __slots__ = ["parent_id", "capacity_block_group_id"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_BLOCK_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    capacity_block_group_id: str
    def __init__(self, parent_id: _Optional[str] = ..., capacity_block_group_id: _Optional[str] = ...) -> None: ...

class CreateCapacityAllowanceRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _capacity_allowance_pb2.CapacityAllowanceSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_capacity_allowance_pb2.CapacityAllowanceSpec, _Mapping]] = ...) -> None: ...

class UpdateCapacityAllowanceRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _capacity_allowance_pb2.CapacityAllowanceSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_capacity_allowance_pb2.CapacityAllowanceSpec, _Mapping]] = ...) -> None: ...

class DeleteCapacityAllowanceRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...
