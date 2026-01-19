from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.mysterybox.v1 import payload_pb2 as _payload_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetPayloadRequest(_message.Message):
    __slots__ = ["secret_id", "version_id"]
    SECRET_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    secret_id: str
    version_id: str
    def __init__(self, secret_id: _Optional[str] = ..., version_id: _Optional[str] = ...) -> None: ...

class GetPayloadByKeyRequest(_message.Message):
    __slots__ = ["secret_id", "version_id", "key"]
    SECRET_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    KEY_FIELD_NUMBER: _ClassVar[int]
    secret_id: str
    version_id: str
    key: str
    def __init__(self, secret_id: _Optional[str] = ..., version_id: _Optional[str] = ..., key: _Optional[str] = ...) -> None: ...

class SecretPayload(_message.Message):
    __slots__ = ["version_id", "data"]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    data: _containers.RepeatedCompositeFieldContainer[_payload_pb2.Payload]
    def __init__(self, version_id: _Optional[str] = ..., data: _Optional[_Iterable[_Union[_payload_pb2.Payload, _Mapping]]] = ...) -> None: ...

class SecretPayloadEntry(_message.Message):
    __slots__ = ["version_id", "data"]
    VERSION_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_FIELD_NUMBER: _ClassVar[int]
    version_id: str
    data: _payload_pb2.Payload
    def __init__(self, version_id: _Optional[str] = ..., data: _Optional[_Union[_payload_pb2.Payload, _Mapping]] = ...) -> None: ...
