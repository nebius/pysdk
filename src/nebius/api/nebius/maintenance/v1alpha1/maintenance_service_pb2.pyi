from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.maintenance.v1alpha1 import maintenance_pb2 as _maintenance_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ListMaintenancesRequest(_message.Message):
    __slots__ = ["parent_id"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    def __init__(self, parent_id: _Optional[str] = ...) -> None: ...

class ListMaintenancesResponse(_message.Message):
    __slots__ = ["items"]
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_maintenance_pb2.Maintenance]
    def __init__(self, items: _Optional[_Iterable[_Union[_maintenance_pb2.Maintenance, _Mapping]]] = ...) -> None: ...

class GetMaintenanceRequest(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...
