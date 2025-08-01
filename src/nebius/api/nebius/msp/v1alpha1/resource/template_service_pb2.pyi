from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ListTemplatesRequest(_message.Message):
    __slots__ = ["page_size", "page_token", "parent_id"]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    page_size: int
    page_token: str
    parent_id: str
    def __init__(self, page_size: _Optional[int] = ..., page_token: _Optional[str] = ..., parent_id: _Optional[str] = ...) -> None: ...

class ListTemplatesResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_template_pb2.Template]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_template_pb2.Template, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
