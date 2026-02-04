from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CORSConfiguration(_message.Message):
    __slots__ = ["rules"]
    RULES_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedCompositeFieldContainer[CORSRule]
    def __init__(self, rules: _Optional[_Iterable[_Union[CORSRule, _Mapping]]] = ...) -> None: ...

class CORSRule(_message.Message):
    __slots__ = ["id", "allowed_headers", "allowed_origins", "allowed_methods", "expose_headers", "max_age_seconds"]
    ID_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_HEADERS_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_ORIGINS_FIELD_NUMBER: _ClassVar[int]
    ALLOWED_METHODS_FIELD_NUMBER: _ClassVar[int]
    EXPOSE_HEADERS_FIELD_NUMBER: _ClassVar[int]
    MAX_AGE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    id: str
    allowed_headers: _containers.RepeatedScalarFieldContainer[str]
    allowed_origins: _containers.RepeatedScalarFieldContainer[str]
    allowed_methods: _containers.RepeatedScalarFieldContainer[str]
    expose_headers: _containers.RepeatedScalarFieldContainer[str]
    max_age_seconds: int
    def __init__(self, id: _Optional[str] = ..., allowed_headers: _Optional[_Iterable[str]] = ..., allowed_origins: _Optional[_Iterable[str]] = ..., allowed_methods: _Optional[_Iterable[str]] = ..., expose_headers: _Optional[_Iterable[str]] = ..., max_age_seconds: _Optional[int] = ...) -> None: ...
