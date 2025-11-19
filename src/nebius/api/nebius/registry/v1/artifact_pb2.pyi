from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Artifact(_message.Message):
    __slots__ = ["id", "name", "media_type", "digest", "size", "status", "type", "created_at", "updated_at", "tags"]
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATUS_UNSPECIFIED: _ClassVar[Artifact.Status]
        ACTIVE: _ClassVar[Artifact.Status]
        DELETING: _ClassVar[Artifact.Status]
    STATUS_UNSPECIFIED: Artifact.Status
    ACTIVE: Artifact.Status
    DELETING: Artifact.Status
    class Type(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        BLOB: _ClassVar[Artifact.Type]
        MANIFEST: _ClassVar[Artifact.Type]
        DEB_PACKAGE: _ClassVar[Artifact.Type]
        MANIFEST_LIST: _ClassVar[Artifact.Type]
        RELEASE_INDEX: _ClassVar[Artifact.Type]
        PACKAGE_INDEX: _ClassVar[Artifact.Type]
        GZIPPED_PACKAGE_INDEX: _ClassVar[Artifact.Type]
    BLOB: Artifact.Type
    MANIFEST: Artifact.Type
    DEB_PACKAGE: Artifact.Type
    MANIFEST_LIST: Artifact.Type
    RELEASE_INDEX: Artifact.Type
    PACKAGE_INDEX: Artifact.Type
    GZIPPED_PACKAGE_INDEX: Artifact.Type
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    MEDIA_TYPE_FIELD_NUMBER: _ClassVar[int]
    DIGEST_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    media_type: str
    digest: str
    size: int
    status: Artifact.Status
    type: Artifact.Type
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    tags: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., media_type: _Optional[str] = ..., digest: _Optional[str] = ..., size: _Optional[int] = ..., status: _Optional[_Union[Artifact.Status, str]] = ..., type: _Optional[_Union[Artifact.Type, str]] = ..., created_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., tags: _Optional[_Iterable[str]] = ...) -> None: ...
