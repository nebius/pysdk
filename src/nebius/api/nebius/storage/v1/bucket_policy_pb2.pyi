from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class BucketPolicy(_message.Message):
    __slots__ = ["rules"]
    class Rule(_message.Message):
        __slots__ = ["paths", "roles", "group_id", "anonymous"]
        class AnonymousAccess(_message.Message):
            __slots__ = []
            def __init__(self) -> None: ...
        PATHS_FIELD_NUMBER: _ClassVar[int]
        ROLES_FIELD_NUMBER: _ClassVar[int]
        GROUP_ID_FIELD_NUMBER: _ClassVar[int]
        ANONYMOUS_FIELD_NUMBER: _ClassVar[int]
        paths: _containers.RepeatedScalarFieldContainer[str]
        roles: _containers.RepeatedScalarFieldContainer[str]
        group_id: str
        anonymous: BucketPolicy.Rule.AnonymousAccess
        def __init__(self, paths: _Optional[_Iterable[str]] = ..., roles: _Optional[_Iterable[str]] = ..., group_id: _Optional[str] = ..., anonymous: _Optional[_Union[BucketPolicy.Rule.AnonymousAccess, _Mapping]] = ...) -> None: ...
    RULES_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedCompositeFieldContainer[BucketPolicy.Rule]
    def __init__(self, rules: _Optional[_Iterable[_Union[BucketPolicy.Rule, _Mapping]]] = ...) -> None: ...
