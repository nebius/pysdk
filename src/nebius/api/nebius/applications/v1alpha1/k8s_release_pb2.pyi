from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class K8sRelease(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: K8sReleaseSpec
    status: K8sReleaseStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[K8sReleaseSpec, _Mapping]] = ..., status: _Optional[_Union[K8sReleaseStatus, _Mapping]] = ...) -> None: ...

class K8sReleaseSpec(_message.Message):
    __slots__ = ["cluster_id", "product_slug", "namespace", "application_name", "values", "set"]
    class SetEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    CLUSTER_ID_FIELD_NUMBER: _ClassVar[int]
    PRODUCT_SLUG_FIELD_NUMBER: _ClassVar[int]
    NAMESPACE_FIELD_NUMBER: _ClassVar[int]
    APPLICATION_NAME_FIELD_NUMBER: _ClassVar[int]
    VALUES_FIELD_NUMBER: _ClassVar[int]
    SET_FIELD_NUMBER: _ClassVar[int]
    cluster_id: str
    product_slug: str
    namespace: str
    application_name: str
    values: str
    set: _containers.ScalarMap[str, str]
    def __init__(self, cluster_id: _Optional[str] = ..., product_slug: _Optional[str] = ..., namespace: _Optional[str] = ..., application_name: _Optional[str] = ..., values: _Optional[str] = ..., set: _Optional[_Mapping[str, str]] = ...) -> None: ...

class K8sReleaseStatus(_message.Message):
    __slots__ = ["state", "error_message"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNSPECIFIED: _ClassVar[K8sReleaseStatus.State]
        CREATED: _ClassVar[K8sReleaseStatus.State]
        RUNNING: _ClassVar[K8sReleaseStatus.State]
        DEPLOYED: _ClassVar[K8sReleaseStatus.State]
        FAILED: _ClassVar[K8sReleaseStatus.State]
        INSTALLING: _ClassVar[K8sReleaseStatus.State]
    UNSPECIFIED: K8sReleaseStatus.State
    CREATED: K8sReleaseStatus.State
    RUNNING: K8sReleaseStatus.State
    DEPLOYED: K8sReleaseStatus.State
    FAILED: K8sReleaseStatus.State
    INSTALLING: K8sReleaseStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    state: K8sReleaseStatus.State
    error_message: str
    def __init__(self, state: _Optional[_Union[K8sReleaseStatus.State, str]] = ..., error_message: _Optional[str] = ...) -> None: ...
