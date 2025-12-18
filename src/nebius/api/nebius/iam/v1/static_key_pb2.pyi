from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.iam.v1 import access_pb2 as _access_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StaticKey(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: StaticKeySpec
    status: StaticKeyStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[StaticKeySpec, _Mapping]] = ..., status: _Optional[_Union[StaticKeyStatus, _Mapping]] = ...) -> None: ...

class StaticKeySpec(_message.Message):
    __slots__ = ["account", "service", "expiresAt"]
    class ClientService(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        CLIENT_SERVICE_UNSPECIFIED: _ClassVar[StaticKeySpec.ClientService]
        OBSERVABILITY: _ClassVar[StaticKeySpec.ClientService]
        CONTAINER_REGISTRY: _ClassVar[StaticKeySpec.ClientService]
        AI_STUDIO: _ClassVar[StaticKeySpec.ClientService]
        TRACTO: _ClassVar[StaticKeySpec.ClientService]
    CLIENT_SERVICE_UNSPECIFIED: StaticKeySpec.ClientService
    OBSERVABILITY: StaticKeySpec.ClientService
    CONTAINER_REGISTRY: StaticKeySpec.ClientService
    AI_STUDIO: StaticKeySpec.ClientService
    TRACTO: StaticKeySpec.ClientService
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    EXPIRESAT_FIELD_NUMBER: _ClassVar[int]
    account: _access_pb2.Account
    service: StaticKeySpec.ClientService
    expiresAt: _timestamp_pb2.Timestamp
    def __init__(self, account: _Optional[_Union[_access_pb2.Account, _Mapping]] = ..., service: _Optional[_Union[StaticKeySpec.ClientService, str]] = ..., expiresAt: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class StaticKeyStatus(_message.Message):
    __slots__ = ["active"]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    active: bool
    def __init__(self, active: bool = ...) -> None: ...
