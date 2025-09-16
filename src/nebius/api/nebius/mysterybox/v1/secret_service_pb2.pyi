from nebius.api.nebius.mysterybox.v1 import secret_pb2 as _secret_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateSecretRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _secret_pb2.SecretSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_secret_pb2.SecretSpec, _Mapping]] = ...) -> None: ...

class UpdateSecretRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _secret_pb2.SecretSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_secret_pb2.SecretSpec, _Mapping]] = ...) -> None: ...

class GetSecretRequest(_message.Message):
    __slots__ = ["id", "show_scheduled_for_deletion"]
    ID_FIELD_NUMBER: _ClassVar[int]
    SHOW_SCHEDULED_FOR_DELETION_FIELD_NUMBER: _ClassVar[int]
    id: str
    show_scheduled_for_deletion: bool
    def __init__(self, id: _Optional[str] = ..., show_scheduled_for_deletion: bool = ...) -> None: ...

class GetSecretByNameRequest(_message.Message):
    __slots__ = ["parent_id", "name"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    name: str
    def __init__(self, parent_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class ListSecretsRequest(_message.Message):
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

class ListSecretsResponse(_message.Message):
    __slots__ = ["next_page_token", "items"]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    next_page_token: str
    items: _containers.RepeatedCompositeFieldContainer[_secret_pb2.Secret]
    def __init__(self, next_page_token: _Optional[str] = ..., items: _Optional[_Iterable[_Union[_secret_pb2.Secret, _Mapping]]] = ...) -> None: ...

class DeleteSecretRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class UndeleteSecretRequest(_message.Message):
    __slots__ = ["id", "name"]
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...
