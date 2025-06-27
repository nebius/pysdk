from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.storage.v1alpha1 import transfer_pb2 as _transfer_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetTransferRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ListTransfersRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListTransfersResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_transfer_pb2.Transfer]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_transfer_pb2.Transfer, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateTransferRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _transfer_pb2.TransferSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_transfer_pb2.TransferSpec, _Mapping]] = ...) -> None: ...

class UpdateTransferRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _transfer_pb2.TransferSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_transfer_pb2.TransferSpec, _Mapping]] = ...) -> None: ...

class StopTransferRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ResumeTransferRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class DeleteTransferRequest(_message.Message):
    __slots__ = ["id", "resource_version"]
    ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    resource_version: int
    def __init__(self, id: _Optional[str] = ..., resource_version: _Optional[int] = ...) -> None: ...

class GetIterationHistoryRequest(_message.Message):
    __slots__ = ["transfer_id", "page_size", "page_token"]
    TRANSFER_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    transfer_id: str
    page_size: int
    page_token: str
    def __init__(self, transfer_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class GetIterationHistoryResponse(_message.Message):
    __slots__ = ["iterations", "next_page_token"]
    ITERATIONS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    iterations: _containers.RepeatedCompositeFieldContainer[_transfer_pb2.TransferIteration]
    next_page_token: str
    def __init__(self, iterations: _Optional[_Iterable[_Union[_transfer_pb2.TransferIteration, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
