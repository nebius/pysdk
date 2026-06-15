from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.kms.v1 import asymmetric_key_pb2 as _asymmetric_key_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateAsymmetricKeyRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _asymmetric_key_pb2.AsymmetricKeySpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_asymmetric_key_pb2.AsymmetricKeySpec, _Mapping]] = ...) -> None: ...

class UpdateAsymmetricKeyRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _asymmetric_key_pb2.AsymmetricKeySpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_asymmetric_key_pb2.AsymmetricKeySpec, _Mapping]] = ...) -> None: ...

class GetAsymmetricKeyRequest(_message.Message):
    __slots__ = ["id", "show_scheduled_for_deletion"]
    ID_FIELD_NUMBER: _ClassVar[int]
    SHOW_SCHEDULED_FOR_DELETION_FIELD_NUMBER: _ClassVar[int]
    id: str
    show_scheduled_for_deletion: bool
    def __init__(self, id: _Optional[str] = ..., show_scheduled_for_deletion: bool = ...) -> None: ...

class GetAsymmetricKeyByNameRequest(_message.Message):
    __slots__ = ["parent_id", "name"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    name: str
    def __init__(self, parent_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class ListAsymmetricKeysRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token", "show_scheduled_for_deletion"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    SHOW_SCHEDULED_FOR_DELETION_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    show_scheduled_for_deletion: bool
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ..., show_scheduled_for_deletion: bool = ...) -> None: ...

class ListAsymmetricKeysResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_asymmetric_key_pb2.AsymmetricKey]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_asymmetric_key_pb2.AsymmetricKey, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class DeleteAsymmetricKeyRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class UpdateAsymmetricKeyDeletionDelayRequest(_message.Message):
    __slots__ = ["id", "deletion_delay"]
    ID_FIELD_NUMBER: _ClassVar[int]
    DELETION_DELAY_FIELD_NUMBER: _ClassVar[int]
    id: str
    deletion_delay: _duration_pb2.Duration
    def __init__(self, id: _Optional[str] = ..., deletion_delay: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ...) -> None: ...

class UndeleteAsymmetricKeyRequest(_message.Message):
    __slots__ = ["id", "name"]
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...
