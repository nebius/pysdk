from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Registry(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: RegistrySpec
    status: RegistryStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[RegistrySpec, _Mapping]] = ..., status: _Optional[_Union[RegistryStatus, _Mapping]] = ...) -> None: ...

class RegistrySpec(_message.Message):
    __slots__ = ["description", "images_count"]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    IMAGES_COUNT_FIELD_NUMBER: _ClassVar[int]
    description: str
    images_count: int
    def __init__(self, description: _Optional[str] = ..., images_count: _Optional[int] = ...) -> None: ...

class RegistryStatus(_message.Message):
    __slots__ = ["state", "images_count", "registry_fqdn"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        CREATING: _ClassVar[RegistryStatus.State]
        ACTIVE: _ClassVar[RegistryStatus.State]
        DELETING: _ClassVar[RegistryStatus.State]
        SUSPENDED: _ClassVar[RegistryStatus.State]
    CREATING: RegistryStatus.State
    ACTIVE: RegistryStatus.State
    DELETING: RegistryStatus.State
    SUSPENDED: RegistryStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    IMAGES_COUNT_FIELD_NUMBER: _ClassVar[int]
    REGISTRY_FQDN_FIELD_NUMBER: _ClassVar[int]
    state: RegistryStatus.State
    images_count: int
    registry_fqdn: str
    def __init__(self, state: _Optional[_Union[RegistryStatus.State, str]] = ..., images_count: _Optional[int] = ..., registry_fqdn: _Optional[str] = ...) -> None: ...
