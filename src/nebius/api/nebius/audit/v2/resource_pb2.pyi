from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.audit.v2 import resource_metadata_pb2 as _resource_metadata_pb2
from nebius.api.nebius.audit.v2 import resource_state_pb2 as _resource_state_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Resource(_message.Message):
    __slots__ = ["metadata", "state", "hierarchy"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    HIERARCHY_FIELD_NUMBER: _ClassVar[int]
    metadata: _resource_metadata_pb2.ResourceMetadata
    state: _resource_state_pb2.ResourceState
    hierarchy: _containers.RepeatedCompositeFieldContainer[_resource_metadata_pb2.ResourceMetadata]
    def __init__(self, metadata: _Optional[_Union[_resource_metadata_pb2.ResourceMetadata, _Mapping]] = ..., state: _Optional[_Union[_resource_state_pb2.ResourceState, _Mapping]] = ..., hierarchy: _Optional[_Iterable[_Union[_resource_metadata_pb2.ResourceMetadata, _Mapping]]] = ...) -> None: ...
