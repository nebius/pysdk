from nebius.api.nebius.storage.v1 import base_pb2 as _base_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CurrentBucketCounters(_message.Message):
    __slots__ = ["simple_objects_quantity", "simple_objects_size", "multipart_objects_quantity", "multipart_objects_size", "multipart_uploads_quantity", "inflight_parts_quantity", "inflight_parts_size"]
    SIMPLE_OBJECTS_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SIMPLE_OBJECTS_SIZE_FIELD_NUMBER: _ClassVar[int]
    MULTIPART_OBJECTS_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    MULTIPART_OBJECTS_SIZE_FIELD_NUMBER: _ClassVar[int]
    MULTIPART_UPLOADS_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    INFLIGHT_PARTS_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    INFLIGHT_PARTS_SIZE_FIELD_NUMBER: _ClassVar[int]
    simple_objects_quantity: int
    simple_objects_size: int
    multipart_objects_quantity: int
    multipart_objects_size: int
    multipart_uploads_quantity: int
    inflight_parts_quantity: int
    inflight_parts_size: int
    def __init__(self, simple_objects_quantity: _Optional[int] = ..., simple_objects_size: _Optional[int] = ..., multipart_objects_quantity: _Optional[int] = ..., multipart_objects_size: _Optional[int] = ..., multipart_uploads_quantity: _Optional[int] = ..., inflight_parts_quantity: _Optional[int] = ..., inflight_parts_size: _Optional[int] = ...) -> None: ...

class NonCurrentBucketCounters(_message.Message):
    __slots__ = ["simple_objects_quantity", "simple_objects_size", "multipart_objects_quantity", "multipart_objects_size"]
    SIMPLE_OBJECTS_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SIMPLE_OBJECTS_SIZE_FIELD_NUMBER: _ClassVar[int]
    MULTIPART_OBJECTS_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    MULTIPART_OBJECTS_SIZE_FIELD_NUMBER: _ClassVar[int]
    simple_objects_quantity: int
    simple_objects_size: int
    multipart_objects_quantity: int
    multipart_objects_size: int
    def __init__(self, simple_objects_quantity: _Optional[int] = ..., simple_objects_size: _Optional[int] = ..., multipart_objects_quantity: _Optional[int] = ..., multipart_objects_size: _Optional[int] = ...) -> None: ...

class BucketCounters(_message.Message):
    __slots__ = ["storage_class", "counters", "non_current_counters"]
    STORAGE_CLASS_FIELD_NUMBER: _ClassVar[int]
    COUNTERS_FIELD_NUMBER: _ClassVar[int]
    NON_CURRENT_COUNTERS_FIELD_NUMBER: _ClassVar[int]
    storage_class: _base_pb2.StorageClass
    counters: CurrentBucketCounters
    non_current_counters: NonCurrentBucketCounters
    def __init__(self, storage_class: _Optional[_Union[_base_pb2.StorageClass, str]] = ..., counters: _Optional[_Union[CurrentBucketCounters, _Mapping]] = ..., non_current_counters: _Optional[_Union[NonCurrentBucketCounters, _Mapping]] = ...) -> None: ...
