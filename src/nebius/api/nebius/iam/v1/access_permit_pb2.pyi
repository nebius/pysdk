from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AccessPermit(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: AccessPermitSpec
    status: AccessPermitStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[AccessPermitSpec, _Mapping]] = ..., status: _Optional[_Union[AccessPermitStatus, _Mapping]] = ...) -> None: ...

class AccessPermitSpec(_message.Message):
    __slots__ = ["resource_id", "role"]
    RESOURCE_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    resource_id: str
    role: str
    def __init__(self, resource_id: _Optional[str] = ..., role: _Optional[str] = ...) -> None: ...

class AccessPermitStatus(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
