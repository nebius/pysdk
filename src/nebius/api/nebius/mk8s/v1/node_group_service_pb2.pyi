from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import empty_pb2 as _empty_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.mk8s.v1 import node_group_pb2 as _node_group_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetNodeGroupCompatibilityMatrixRequest(_message.Message):
    __slots__ = ["cluster_kubernetes_version", "platform"]
    CLUSTER_KUBERNETES_VERSION_FIELD_NUMBER: _ClassVar[int]
    PLATFORM_FIELD_NUMBER: _ClassVar[int]
    cluster_kubernetes_version: str
    platform: str
    def __init__(self, cluster_kubernetes_version: _Optional[str] = ..., platform: _Optional[str] = ...) -> None: ...

class NodeGroupCompatibilityMatrix(_message.Message):
    __slots__ = ["versions"]
    VERSIONS_FIELD_NUMBER: _ClassVar[int]
    versions: _containers.RepeatedCompositeFieldContainer[NodeGroupCompatibilityVersion]
    def __init__(self, versions: _Optional[_Iterable[_Union[NodeGroupCompatibilityVersion, _Mapping]]] = ...) -> None: ...

class NodeGroupCompatibilityVersion(_message.Message):
    __slots__ = ["kubernetes_version", "items"]
    KUBERNETES_VERSION_FIELD_NUMBER: _ClassVar[int]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    kubernetes_version: str
    items: _containers.RepeatedCompositeFieldContainer[NodeGroupCompatibilityVersionItem]
    def __init__(self, kubernetes_version: _Optional[str] = ..., items: _Optional[_Iterable[_Union[NodeGroupCompatibilityVersionItem, _Mapping]]] = ...) -> None: ...

class NodeGroupCompatibilityVersionItem(_message.Message):
    __slots__ = ["os", "drivers_preset", "compatible_platforms"]
    OS_FIELD_NUMBER: _ClassVar[int]
    DRIVERS_PRESET_FIELD_NUMBER: _ClassVar[int]
    COMPATIBLE_PLATFORMS_FIELD_NUMBER: _ClassVar[int]
    os: str
    drivers_preset: str
    compatible_platforms: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, os: _Optional[str] = ..., drivers_preset: _Optional[str] = ..., compatible_platforms: _Optional[_Iterable[str]] = ...) -> None: ...

class CreateNodeGroupRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _node_group_pb2.NodeGroupSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_node_group_pb2.NodeGroupSpec, _Mapping]] = ...) -> None: ...

class GetNodeGroupRequest(_message.Message):
    __slots__ = ["id", "resource_version"]
    ID_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    resource_version: str
    def __init__(self, id: _Optional[str] = ..., resource_version: _Optional[str] = ...) -> None: ...

class ListNodeGroupsRequest(_message.Message):
    __slots__ = ["parent_id", "page_size", "page_token"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    page_size: int
    page_token: str
    def __init__(self, parent_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListNodeGroupsResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_node_group_pb2.NodeGroup]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_node_group_pb2.NodeGroup, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class UpdateNodeGroupRequest(_message.Message):
    __slots__ = ["metadata", "spec"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _node_group_pb2.NodeGroupSpec
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_node_group_pb2.NodeGroupSpec, _Mapping]] = ...) -> None: ...

class DeleteNodeGroupRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class UpgradeNodeGroupRequest(_message.Message):
    __slots__ = ["id", "latest_infra_version"]
    ID_FIELD_NUMBER: _ClassVar[int]
    LATEST_INFRA_VERSION_FIELD_NUMBER: _ClassVar[int]
    id: str
    latest_infra_version: _empty_pb2.Empty
    def __init__(self, id: _Optional[str] = ..., latest_infra_version: _Optional[_Union[_empty_pb2.Empty, _Mapping]] = ...) -> None: ...
