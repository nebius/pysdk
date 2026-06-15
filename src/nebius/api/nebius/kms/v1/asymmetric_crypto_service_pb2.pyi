from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class AsymmetricSignHashRequest(_message.Message):
    __slots__ = ["key_id", "hash"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    HASH_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    hash: bytes
    def __init__(self, key_id: _Optional[str] = ..., hash: _Optional[bytes] = ...) -> None: ...

class AsymmetricSignHashResponse(_message.Message):
    __slots__ = ["key_id", "signature"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    signature: bytes
    def __init__(self, key_id: _Optional[str] = ..., signature: _Optional[bytes] = ...) -> None: ...

class AsymmetricGetPublicKeyRequest(_message.Message):
    __slots__ = ["key_id"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    def __init__(self, key_id: _Optional[str] = ...) -> None: ...

class AsymmetricGetPublicKeyResponse(_message.Message):
    __slots__ = ["key_id", "public_key"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    public_key: str
    def __init__(self, key_id: _Optional[str] = ..., public_key: _Optional[str] = ...) -> None: ...

class AsymmetricDecryptRequest(_message.Message):
    __slots__ = ["key_id", "ciphertext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    CIPHERTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    ciphertext: bytes
    def __init__(self, key_id: _Optional[str] = ..., ciphertext: _Optional[bytes] = ...) -> None: ...

class AsymmetricDecryptResponse(_message.Message):
    __slots__ = ["key_id", "plaintext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    PLAINTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    plaintext: bytes
    def __init__(self, key_id: _Optional[str] = ..., plaintext: _Optional[bytes] = ...) -> None: ...
