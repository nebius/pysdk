from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1alpha1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.common.v1alpha1 import operation_service_pb2 as _operation_service_pb2
from nebius.api.nebius.compute.v1alpha1 import filesystem_pb2 as _filesystem_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetFilesystemRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListFilesystemsRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token", "filter"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    filter: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ..., filter: _Optional[str] = ...) -> None: ...

class CreateFilesystemRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _filesystem_pb2.FilesystemSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_filesystem_pb2.FilesystemSpec, _Mapping]] = ...) -> None: ...

class UpdateFilesystemRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _filesystem_pb2.FilesystemSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_filesystem_pb2.FilesystemSpec, _Mapping]] = ...) -> None: ...

class DeleteFilesystemRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListFilesystemsResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_filesystem_pb2.Filesystem]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_filesystem_pb2.Filesystem, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
