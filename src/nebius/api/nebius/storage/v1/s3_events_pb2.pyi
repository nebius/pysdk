from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CompleteMultipartUploadRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "object_key", "parts"]
    class Part(_message.Message):
        __slots__ = ["part_number", "etag"]
        PART_NUMBER_FIELD_NUMBER: _ClassVar[int]
        ETAG_FIELD_NUMBER: _ClassVar[int]
        part_number: int
        etag: str
        def __init__(self, part_number: _Optional[int] = ..., etag: _Optional[str] = ...) -> None: ...
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    PARTS_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    object_key: str
    parts: _containers.RepeatedCompositeFieldContainer[CompleteMultipartUploadRequestParameters.Part]
    def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ..., parts: _Optional[_Iterable[_Union[CompleteMultipartUploadRequestParameters.Part, _Mapping]]] = ...) -> None: ...

class CompleteMultipartUploadResponse(_message.Message):
    __slots__ = ["bucket_name", "object_key", "etag"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    ETAG_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    object_key: str
    etag: str
    def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ..., etag: _Optional[str] = ...) -> None: ...

class CopyObjectRequestParameters(_message.Message):
    __slots__ = ["source", "target"]
    class Source(_message.Message):
        __slots__ = ["bucket_name", "object_key", "version"]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
        VERSION_FIELD_NUMBER: _ClassVar[int]
        bucket_name: str
        object_key: str
        version: str
        def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...
    class Target(_message.Message):
        __slots__ = ["bucket_name", "object_key"]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
        bucket_name: str
        object_key: str
        def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ...) -> None: ...
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    TARGET_FIELD_NUMBER: _ClassVar[int]
    source: CopyObjectRequestParameters.Source
    target: CopyObjectRequestParameters.Target
    def __init__(self, source: _Optional[_Union[CopyObjectRequestParameters.Source, _Mapping]] = ..., target: _Optional[_Union[CopyObjectRequestParameters.Target, _Mapping]] = ...) -> None: ...

class CopyObjectResponse(_message.Message):
    __slots__ = ["etag", "last_modified"]
    ETAG_FIELD_NUMBER: _ClassVar[int]
    LAST_MODIFIED_FIELD_NUMBER: _ClassVar[int]
    etag: str
    last_modified: _timestamp_pb2.Timestamp
    def __init__(self, etag: _Optional[str] = ..., last_modified: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class DeleteObjectRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "object_key", "version"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    object_key: str
    version: str
    def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class DeleteObjectResponse(_message.Message):
    __slots__ = ["delete_marker"]
    DELETE_MARKER_FIELD_NUMBER: _ClassVar[int]
    delete_marker: bool
    def __init__(self, delete_marker: bool = ...) -> None: ...

class DeleteObjectsRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "objects"]
    class ObjectKey(_message.Message):
        __slots__ = ["key", "version"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VERSION_FIELD_NUMBER: _ClassVar[int]
        key: str
        version: str
        def __init__(self, key: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECTS_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    objects: _containers.RepeatedCompositeFieldContainer[DeleteObjectsRequestParameters.ObjectKey]
    def __init__(self, bucket_name: _Optional[str] = ..., objects: _Optional[_Iterable[_Union[DeleteObjectsRequestParameters.ObjectKey, _Mapping]]] = ...) -> None: ...

class DeleteObjectsResponse(_message.Message):
    __slots__ = ["deleted", "errors"]
    class DeleteSuccess(_message.Message):
        __slots__ = ["delete_marker", "object_key", "version"]
        DELETE_MARKER_FIELD_NUMBER: _ClassVar[int]
        OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
        VERSION_FIELD_NUMBER: _ClassVar[int]
        delete_marker: bool
        object_key: str
        version: str
        def __init__(self, delete_marker: bool = ..., object_key: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...
    class DeleteError(_message.Message):
        __slots__ = ["code", "message", "object_key", "version"]
        CODE_FIELD_NUMBER: _ClassVar[int]
        MESSAGE_FIELD_NUMBER: _ClassVar[int]
        OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
        VERSION_FIELD_NUMBER: _ClassVar[int]
        code: str
        message: str
        object_key: str
        version: str
        def __init__(self, code: _Optional[str] = ..., message: _Optional[str] = ..., object_key: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...
    DELETED_FIELD_NUMBER: _ClassVar[int]
    ERRORS_FIELD_NUMBER: _ClassVar[int]
    deleted: _containers.RepeatedCompositeFieldContainer[DeleteObjectsResponse.DeleteSuccess]
    errors: _containers.RepeatedCompositeFieldContainer[DeleteObjectsResponse.DeleteError]
    def __init__(self, deleted: _Optional[_Iterable[_Union[DeleteObjectsResponse.DeleteSuccess, _Mapping]]] = ..., errors: _Optional[_Iterable[_Union[DeleteObjectsResponse.DeleteError, _Mapping]]] = ...) -> None: ...

class ObjectRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "object_key", "version"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    object_key: str
    version: str
    def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class ObjectResponse(_message.Message):
    __slots__ = ["etag", "version", "last_modified"]
    ETAG_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    LAST_MODIFIED_FIELD_NUMBER: _ClassVar[int]
    etag: str
    version: str
    last_modified: _timestamp_pb2.Timestamp
    def __init__(self, etag: _Optional[str] = ..., version: _Optional[str] = ..., last_modified: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ListObjectVersionsRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "prefix", "key_marker", "version_id_marker", "limit", "delimiter"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    KEY_MARKER_FIELD_NUMBER: _ClassVar[int]
    VERSION_ID_MARKER_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    DELIMITER_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    prefix: str
    key_marker: str
    version_id_marker: int
    limit: int
    delimiter: str
    def __init__(self, bucket_name: _Optional[str] = ..., prefix: _Optional[str] = ..., key_marker: _Optional[str] = ..., version_id_marker: _Optional[int] = ..., limit: _Optional[int] = ..., delimiter: _Optional[str] = ...) -> None: ...

class ListObjectVersionsResponse(_message.Message):
    __slots__ = ["versions", "delete_markers", "common_prefixes", "truncated", "next_key_marker", "next_version_id_marker"]
    class VersionView(_message.Message):
        __slots__ = ["etag", "latest", "object_key", "last_modified", "size", "version_id", "storage_class"]
        ETAG_FIELD_NUMBER: _ClassVar[int]
        LATEST_FIELD_NUMBER: _ClassVar[int]
        OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
        LAST_MODIFIED_FIELD_NUMBER: _ClassVar[int]
        SIZE_FIELD_NUMBER: _ClassVar[int]
        VERSION_ID_FIELD_NUMBER: _ClassVar[int]
        STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
        etag: str
        latest: bool
        object_key: str
        last_modified: _timestamp_pb2.Timestamp
        size: int
        version_id: str
        storage_class: str
        def __init__(self, etag: _Optional[str] = ..., latest: bool = ..., object_key: _Optional[str] = ..., last_modified: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., size: _Optional[int] = ..., version_id: _Optional[str] = ..., storage_class: _Optional[str] = ...) -> None: ...
    class DeleteMarkerView(_message.Message):
        __slots__ = ["latest", "object_key", "last_modified", "version_id"]
        LATEST_FIELD_NUMBER: _ClassVar[int]
        OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
        LAST_MODIFIED_FIELD_NUMBER: _ClassVar[int]
        VERSION_ID_FIELD_NUMBER: _ClassVar[int]
        latest: bool
        object_key: str
        last_modified: _timestamp_pb2.Timestamp
        version_id: str
        def __init__(self, latest: bool = ..., object_key: _Optional[str] = ..., last_modified: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., version_id: _Optional[str] = ...) -> None: ...
    VERSIONS_FIELD_NUMBER: _ClassVar[int]
    DELETE_MARKERS_FIELD_NUMBER: _ClassVar[int]
    COMMON_PREFIXES_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    NEXT_KEY_MARKER_FIELD_NUMBER: _ClassVar[int]
    NEXT_VERSION_ID_MARKER_FIELD_NUMBER: _ClassVar[int]
    versions: _containers.RepeatedCompositeFieldContainer[ListObjectVersionsResponse.VersionView]
    delete_markers: _containers.RepeatedCompositeFieldContainer[ListObjectVersionsResponse.DeleteMarkerView]
    common_prefixes: _containers.RepeatedScalarFieldContainer[str]
    truncated: bool
    next_key_marker: str
    next_version_id_marker: int
    def __init__(self, versions: _Optional[_Iterable[_Union[ListObjectVersionsResponse.VersionView, _Mapping]]] = ..., delete_markers: _Optional[_Iterable[_Union[ListObjectVersionsResponse.DeleteMarkerView, _Mapping]]] = ..., common_prefixes: _Optional[_Iterable[str]] = ..., truncated: bool = ..., next_key_marker: _Optional[str] = ..., next_version_id_marker: _Optional[int] = ...) -> None: ...

class ListObjectsRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "prefix", "delimiter", "start_after", "limit"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    DELIMITER_FIELD_NUMBER: _ClassVar[int]
    START_AFTER_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    prefix: str
    delimiter: str
    start_after: str
    limit: int
    def __init__(self, bucket_name: _Optional[str] = ..., prefix: _Optional[str] = ..., delimiter: _Optional[str] = ..., start_after: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class ListObjectsResponse(_message.Message):
    __slots__ = ["objects", "common_prefixes", "truncated"]
    class ObjectView(_message.Message):
        __slots__ = ["etag", "object_key", "last_modified", "size", "storage_class"]
        ETAG_FIELD_NUMBER: _ClassVar[int]
        OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
        LAST_MODIFIED_FIELD_NUMBER: _ClassVar[int]
        SIZE_FIELD_NUMBER: _ClassVar[int]
        STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
        etag: str
        object_key: str
        last_modified: _timestamp_pb2.Timestamp
        size: int
        storage_class: str
        def __init__(self, etag: _Optional[str] = ..., object_key: _Optional[str] = ..., last_modified: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., size: _Optional[int] = ..., storage_class: _Optional[str] = ...) -> None: ...
    OBJECTS_FIELD_NUMBER: _ClassVar[int]
    COMMON_PREFIXES_FIELD_NUMBER: _ClassVar[int]
    TRUNCATED_FIELD_NUMBER: _ClassVar[int]
    objects: _containers.RepeatedCompositeFieldContainer[ListObjectsResponse.ObjectView]
    common_prefixes: _containers.RepeatedScalarFieldContainer[str]
    truncated: bool
    def __init__(self, objects: _Optional[_Iterable[_Union[ListObjectsResponse.ObjectView, _Mapping]]] = ..., common_prefixes: _Optional[_Iterable[str]] = ..., truncated: bool = ...) -> None: ...

class PostObjectRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "object_key", "size"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    object_key: str
    size: int
    def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ..., size: _Optional[int] = ...) -> None: ...

class PostObjectResponse(_message.Message):
    __slots__ = ["etag", "version"]
    ETAG_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    etag: str
    version: str
    def __init__(self, etag: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class PutObjectRequestParameters(_message.Message):
    __slots__ = ["bucket_name", "object_key", "size", "storage_class", "expected_md5"]
    BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
    OBJECT_KEY_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
    EXPECTED_MD5_FIELD_NUMBER: _ClassVar[int]
    bucket_name: str
    object_key: str
    size: int
    storage_class: str
    expected_md5: str
    def __init__(self, bucket_name: _Optional[str] = ..., object_key: _Optional[str] = ..., size: _Optional[int] = ..., storage_class: _Optional[str] = ..., expected_md5: _Optional[str] = ...) -> None: ...

class PutObjectResponse(_message.Message):
    __slots__ = ["etag", "version"]
    ETAG_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    etag: str
    version: str
    def __init__(self, etag: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...
