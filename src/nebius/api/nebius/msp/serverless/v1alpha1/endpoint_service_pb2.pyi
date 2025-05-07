from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.common.v1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.msp.serverless.v1alpha1 import endpoint_pb2 as _endpoint_pb2
from nebius.api.nebius.msp.v1alpha1 import common_pb2 as _common_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class CreateEndpointRequest(_message.Message):
    __slots__ = ["metadata", "spec", "dry_run"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    DRY_RUN_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: _endpoint_pb2.EndpointSpec
    dry_run: bool
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[_endpoint_pb2.EndpointSpec, _Mapping]] = ..., dry_run: bool = ...) -> None: ...

class ListEndpointsResponse(_message.Message):
    __slots__ = ["items", "next_page_token"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_endpoint_pb2.Endpoint]
    next_page_token: str
    def __init__(self, items: _Optional[_Iterable[_Union[_endpoint_pb2.Endpoint, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
