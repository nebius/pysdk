from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.example.compute.v1alpha1 import instance_pb2 as _instance_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class InstanceView(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BASIC: _ClassVar[InstanceView]
    FULL: _ClassVar[InstanceView]
BASIC: InstanceView
FULL: InstanceView

class GetInstanceRequest(_message.Message):
    __slots__ = ("id", "view", "resource_version")
    ID_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    view: InstanceView
    resource_version: str
    def __init__(self, id: _Optional[str] = ..., view: _Optional[_Union[InstanceView, str]] = ..., resource_version: _Optional[str] = ...) -> None: ...

class ListInstancesRequest(_message.Message):
    __slots__ = ("project_id", "page_size", "page_token", "filter", "view")
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    FILTER_FIELD_NUMBER: _ClassVar[int]
    VIEW_FIELD_NUMBER: _ClassVar[int]
    project_id: str
    page_size: int
    page_token: str
    filter: str
    view: InstanceView
    def __init__(self, project_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ..., filter: _Optional[str] = ..., view: _Optional[_Union[InstanceView, str]] = ...) -> None: ...

class ListInstancesResponse(_message.Message):
    __slots__ = ("items", "next_page_token")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_instance_pb2.Instance]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_instance_pb2.Instance, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class CreateInstanceRequest(_message.Message):
    __slots__ = ("metadata", "spec")
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _instance_pb2.InstanceSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_instance_pb2.InstanceSpec, _Mapping]] = ...) -> None: ...

class UpdateInstanceRequest(_message.Message):
    __slots__ = ("metadata", "spec")
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _instance_pb2.InstanceSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_instance_pb2.InstanceSpec, _Mapping]] = ...) -> None: ...

class DeleteInstanceRequest(_message.Message):
    __slots__ = ("id", "resource_version")
    ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    resource_version: str
    def __init__(self, id: _Optional[str] = ..., resource_version: _Optional[str] = ...) -> None: ...

class StopInstanceRequest(_message.Message):
    __slots__ = ("instance_id", "force", "termination_grace_period", "compute_node")
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    FORCE_FIELD_NUMBER: _ClassVar[int]
    TERMINATION_GRACE_PERIOD_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_NODE_FIELD_NUMBER: _ClassVar[int]
    instance_id: str
    force: bool
    termination_grace_period: _duration_pb2.Duration
    compute_node: str
    def __init__(self, instance_id: _Optional[str] = ..., force: bool = ..., termination_grace_period: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., compute_node: _Optional[str] = ...) -> None: ...

class StartInstanceRequest(_message.Message):
    __slots__ = ("instance_id", "override_force_deallocated")
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_FORCE_DEALLOCATED_FIELD_NUMBER: _ClassVar[int]
    instance_id: str
    override_force_deallocated: bool
    def __init__(self, instance_id: _Optional[str] = ..., override_force_deallocated: bool = ...) -> None: ...
