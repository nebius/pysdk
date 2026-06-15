from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.kms.v1 import symmetric_key_pb2 as _symmetric_key_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SymmetricEncryptRequest(_message.Message):
    __slots__ = ["key_id", "aad_context", "plaintext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    AAD_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    PLAINTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    aad_context: bytes
    plaintext: bytes
    def __init__(self, key_id: _Optional[str] = ..., aad_context: _Optional[bytes] = ..., plaintext: _Optional[bytes] = ...) -> None: ...

class SymmetricEncryptResponse(_message.Message):
    __slots__ = ["key_id", "ciphertext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    CIPHERTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    ciphertext: bytes
    def __init__(self, key_id: _Optional[str] = ..., ciphertext: _Optional[bytes] = ...) -> None: ...

class SymmetricDecryptRequest(_message.Message):
    __slots__ = ["key_id", "aad_context", "ciphertext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    AAD_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    CIPHERTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    aad_context: bytes
    ciphertext: bytes
    def __init__(self, key_id: _Optional[str] = ..., aad_context: _Optional[bytes] = ..., ciphertext: _Optional[bytes] = ...) -> None: ...

class SymmetricDecryptResponse(_message.Message):
    __slots__ = ["key_id", "plaintext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    PLAINTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    plaintext: bytes
    def __init__(self, key_id: _Optional[str] = ..., plaintext: _Optional[bytes] = ...) -> None: ...

class GenerateDataKeyRequest(_message.Message):
    __slots__ = ["key_id", "aad_context", "data_key_spec", "skip_plaintext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    AAD_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    DATA_KEY_SPEC_FIELD_NUMBER: _ClassVar[int]
    SKIP_PLAINTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    aad_context: bytes
    data_key_spec: _symmetric_key_pb2.SymmetricAlgorithm
    skip_plaintext: bool
    def __init__(self, key_id: _Optional[str] = ..., aad_context: _Optional[bytes] = ..., data_key_spec: _Optional[_Union[_symmetric_key_pb2.SymmetricAlgorithm, str]] = ..., skip_plaintext: bool = ...) -> None: ...

class GenerateDataKeyResponse(_message.Message):
    __slots__ = ["key_id", "data_key_plaintext", "data_key_ciphertext"]
    KEY_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_KEY_PLAINTEXT_FIELD_NUMBER: _ClassVar[int]
    DATA_KEY_CIPHERTEXT_FIELD_NUMBER: _ClassVar[int]
    key_id: str
    data_key_plaintext: bytes
    data_key_ciphertext: bytes
    def __init__(self, key_id: _Optional[str] = ..., data_key_plaintext: _Optional[bytes] = ..., data_key_ciphertext: _Optional[bytes] = ...) -> None: ...
