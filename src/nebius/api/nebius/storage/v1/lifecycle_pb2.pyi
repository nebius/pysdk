from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.storage.v1 import base_pb2 as _base_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LifecycleConfiguration(_message.Message):
    __slots__ = ["rules", "last_access_filter"]
    RULES_FIELD_NUMBER: _ClassVar[int]
    LAST_ACCESS_FILTER_FIELD_NUMBER: _ClassVar[int]
    rules: _containers.RepeatedCompositeFieldContainer[LifecycleRule]
    last_access_filter: LifecycleAccessFilter
    def __init__(self, rules: _Optional[_Iterable[_Union[LifecycleRule, _Mapping]]] = ..., last_access_filter: _Optional[_Union[LifecycleAccessFilter, _Mapping]] = ...) -> None: ...

class LifecycleRule(_message.Message):
    __slots__ = ["id", "status", "filter", "expiration", "noncurrent_version_expiration", "abort_incomplete_multipart_upload", "transition", "noncurrent_version_transition"]
    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATUS_UNSPECIFIED: _ClassVar[LifecycleRule.Status]
        ENABLED: _ClassVar[LifecycleRule.Status]
        DISABLED: _ClassVar[LifecycleRule.Status]
    STATUS_UNSPECIFIED: LifecycleRule.Status
    ENABLED: LifecycleRule.Status
    DISABLED: LifecycleRule.Status
    ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    EXPIRATION_FIELD_NUMBER: _ClassVar[int]
    NONCURRENT_VERSION_EXPIRATION_FIELD_NUMBER: _ClassVar[int]
    ABORT_INCOMPLETE_MULTIPART_UPLOAD_FIELD_NUMBER: _ClassVar[int]
    TRANSITION_FIELD_NUMBER: _ClassVar[int]
    NONCURRENT_VERSION_TRANSITION_FIELD_NUMBER: _ClassVar[int]
    id: str
    status: LifecycleRule.Status
    filter: LifecycleFilter
    expiration: LifecycleExpiration
    noncurrent_version_expiration: LifecycleNoncurrentVersionExpiration
    abort_incomplete_multipart_upload: LifecycleAbortIncompleteMultipartUpload
    transition: LifecycleTransition
    noncurrent_version_transition: LifecycleNoncurrentVersionTransition
    def __init__(self, id: _Optional[str] = ..., status: _Optional[_Union[LifecycleRule.Status, str]] = ..., filter: _Optional[_Union[LifecycleFilter, _Mapping]] = ..., expiration: _Optional[_Union[LifecycleExpiration, _Mapping]] = ..., noncurrent_version_expiration: _Optional[_Union[LifecycleNoncurrentVersionExpiration, _Mapping]] = ..., abort_incomplete_multipart_upload: _Optional[_Union[LifecycleAbortIncompleteMultipartUpload, _Mapping]] = ..., transition: _Optional[_Union[LifecycleTransition, _Mapping]] = ..., noncurrent_version_transition: _Optional[_Union[LifecycleNoncurrentVersionTransition, _Mapping]] = ...) -> None: ...

class LifecycleFilter(_message.Message):
    __slots__ = ["prefix", "object_size_greater_than_bytes", "object_size_less_than_bytes"]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    OBJECT_SIZE_GREATER_THAN_BYTES_FIELD_NUMBER: _ClassVar[int]
    OBJECT_SIZE_LESS_THAN_BYTES_FIELD_NUMBER: _ClassVar[int]
    prefix: str
    object_size_greater_than_bytes: int
    object_size_less_than_bytes: int
    def __init__(self, prefix: _Optional[str] = ..., object_size_greater_than_bytes: _Optional[int] = ..., object_size_less_than_bytes: _Optional[int] = ...) -> None: ...

class LifecycleAccessFilter(_message.Message):
    __slots__ = ["conditions"]
    class Condition(_message.Message):
        __slots__ = ["type", "methods", "user_agents"]
        class Type(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = []
            TYPE_UNSPECIFIED: _ClassVar[LifecycleAccessFilter.Condition.Type]
            INCLUDE: _ClassVar[LifecycleAccessFilter.Condition.Type]
            EXCLUDE: _ClassVar[LifecycleAccessFilter.Condition.Type]
        TYPE_UNSPECIFIED: LifecycleAccessFilter.Condition.Type
        INCLUDE: LifecycleAccessFilter.Condition.Type
        EXCLUDE: LifecycleAccessFilter.Condition.Type
        class Method(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
            __slots__ = []
            METHOD_UNSPECIFIED: _ClassVar[LifecycleAccessFilter.Condition.Method]
            GET_OBJECT: _ClassVar[LifecycleAccessFilter.Condition.Method]
            HEAD_OBJECT: _ClassVar[LifecycleAccessFilter.Condition.Method]
            GET_OBJECT_TAGGING: _ClassVar[LifecycleAccessFilter.Condition.Method]
            COPY_OBJECT: _ClassVar[LifecycleAccessFilter.Condition.Method]
            UPLOAD_PART_COPY: _ClassVar[LifecycleAccessFilter.Condition.Method]
        METHOD_UNSPECIFIED: LifecycleAccessFilter.Condition.Method
        GET_OBJECT: LifecycleAccessFilter.Condition.Method
        HEAD_OBJECT: LifecycleAccessFilter.Condition.Method
        GET_OBJECT_TAGGING: LifecycleAccessFilter.Condition.Method
        COPY_OBJECT: LifecycleAccessFilter.Condition.Method
        UPLOAD_PART_COPY: LifecycleAccessFilter.Condition.Method
        TYPE_FIELD_NUMBER: _ClassVar[int]
        METHODS_FIELD_NUMBER: _ClassVar[int]
        USER_AGENTS_FIELD_NUMBER: _ClassVar[int]
        type: LifecycleAccessFilter.Condition.Type
        methods: _containers.RepeatedScalarFieldContainer[LifecycleAccessFilter.Condition.Method]
        user_agents: _containers.RepeatedScalarFieldContainer[str]
        def __init__(self, type: _Optional[_Union[LifecycleAccessFilter.Condition.Type, str]] = ..., methods: _Optional[_Iterable[_Union[LifecycleAccessFilter.Condition.Method, str]]] = ..., user_agents: _Optional[_Iterable[str]] = ...) -> None: ...
    CONDITIONS_FIELD_NUMBER: _ClassVar[int]
    conditions: _containers.RepeatedCompositeFieldContainer[LifecycleAccessFilter.Condition]
    def __init__(self, conditions: _Optional[_Iterable[_Union[LifecycleAccessFilter.Condition, _Mapping]]] = ...) -> None: ...

class LifecycleExpiration(_message.Message):
    __slots__ = ["date", "days", "expired_object_delete_marker"]
    DATE_FIELD_NUMBER: _ClassVar[int]
    DAYS_FIELD_NUMBER: _ClassVar[int]
    EXPIRED_OBJECT_DELETE_MARKER_FIELD_NUMBER: _ClassVar[int]
    date: _timestamp_pb2.Timestamp
    days: int
    expired_object_delete_marker: bool
    def __init__(self, date: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., days: _Optional[int] = ..., expired_object_delete_marker: bool = ...) -> None: ...

class LifecycleNoncurrentVersionExpiration(_message.Message):
    __slots__ = ["newer_noncurrent_versions", "noncurrent_days"]
    NEWER_NONCURRENT_VERSIONS_FIELD_NUMBER: _ClassVar[int]
    NONCURRENT_DAYS_FIELD_NUMBER: _ClassVar[int]
    newer_noncurrent_versions: int
    noncurrent_days: int
    def __init__(self, newer_noncurrent_versions: _Optional[int] = ..., noncurrent_days: _Optional[int] = ...) -> None: ...

class LifecycleAbortIncompleteMultipartUpload(_message.Message):
    __slots__ = ["days_after_initiation"]
    DAYS_AFTER_INITIATION_FIELD_NUMBER: _ClassVar[int]
    days_after_initiation: int
    def __init__(self, days_after_initiation: _Optional[int] = ...) -> None: ...

class LifecycleTransition(_message.Message):
    __slots__ = ["date", "days", "days_since_last_access", "storage_class"]
    DATE_FIELD_NUMBER: _ClassVar[int]
    DAYS_FIELD_NUMBER: _ClassVar[int]
    DAYS_SINCE_LAST_ACCESS_FIELD_NUMBER: _ClassVar[int]
    STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
    date: _timestamp_pb2.Timestamp
    days: int
    days_since_last_access: int
    storage_class: _base_pb2.StorageClass
    def __init__(self, date: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., days: _Optional[int] = ..., days_since_last_access: _Optional[int] = ..., storage_class: _Optional[_Union[_base_pb2.StorageClass, str]] = ...) -> None: ...

class LifecycleNoncurrentVersionTransition(_message.Message):
    __slots__ = ["newer_noncurrent_versions", "noncurrent_days", "storage_class"]
    NEWER_NONCURRENT_VERSIONS_FIELD_NUMBER: _ClassVar[int]
    NONCURRENT_DAYS_FIELD_NUMBER: _ClassVar[int]
    STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
    newer_noncurrent_versions: int
    noncurrent_days: int
    storage_class: _base_pb2.StorageClass
    def __init__(self, newer_noncurrent_versions: _Optional[int] = ..., noncurrent_days: _Optional[int] = ..., storage_class: _Optional[_Union[_base_pb2.StorageClass, str]] = ...) -> None: ...
