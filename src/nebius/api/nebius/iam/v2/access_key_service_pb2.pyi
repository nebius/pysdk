from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.iam.v1 import access_pb2 as _access_pb2
from nebius.api.nebius.iam.v2 import access_key_pb2 as _access_key_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateAccessKeyRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _access_key_pb2.AccessKeySpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_access_key_pb2.AccessKeySpec, _Mapping]] = ...) -> None: ...

class GetAccessKeyRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetAccessKeySecretRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetAccessKeyByAwsIdRequest(_message.Message):
    __slots__ = ["aws_access_key_id"]
    AWS_ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    aws_access_key_id: str
    def __init__(self, aws_access_key_id: _Optional[str] = ...) -> None: ...

class ListAccessKeysRequest(_message.Message):
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

class ListAccessKeysByAccountRequest(_message.Message):
    __slots__ = ["account", "page_size", "page_token", "filter"]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    account: _access_pb2.Account
    page_size: int
    page_token: str
    filter: str
    def __init__(self, account: _Optional[_Union[_access_pb2.Account, _Mapping]] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ..., filter: _Optional[str] = ...) -> None: ...

class UpdateAccessKeyRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _access_key_pb2.AccessKeySpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_access_key_pb2.AccessKeySpec, _Mapping]] = ...) -> None: ...

class ActivateAccessKeyRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class DeactivateAccessKeyRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class ActivateAccessKeyByAwsIdRequest(_message.Message):
    __slots__ = ["aws_access_key_id"]
    AWS_ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    aws_access_key_id: str
    def __init__(self, aws_access_key_id: _Optional[str] = ...) -> None: ...

class DeactivateAccessKeyByAwsIdRequest(_message.Message):
    __slots__ = ["aws_access_key_id"]
    AWS_ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    aws_access_key_id: str
    def __init__(self, aws_access_key_id: _Optional[str] = ...) -> None: ...

class DeleteAccessKeyRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class DeleteAccessKeyByAwsIdRequest(_message.Message):
    __slots__ = ["aws_access_key_id"]
    AWS_ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    aws_access_key_id: str
    def __init__(self, aws_access_key_id: _Optional[str] = ...) -> None: ...

class GetAccessKeySecretResponse(_message.Message):
    __slots__ = ["aws_access_key_id", "secret"]
    AWS_ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    SECRET_FIELD_NUMBER: _ClassVar[int]
    aws_access_key_id: str
    secret: str
    def __init__(self, aws_access_key_id: _Optional[str] = ..., secret: _Optional[str] = ...) -> None: ...

class ListAccessKeysResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_access_key_pb2.AccessKey]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_access_key_pb2.AccessKey, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
