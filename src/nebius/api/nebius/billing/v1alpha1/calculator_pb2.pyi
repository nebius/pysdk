from nebius.api.nebius.compute.v1 import disk_service_pb2 as _disk_service_pb2
from nebius.api.nebius.compute.v1 import filesystem_service_pb2 as _filesystem_service_pb2
from nebius.api.nebius.compute.v1 import instance_service_pb2 as _instance_service_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceSpec(_message.Message):
    __slots__ = ["compute_instance_spec", "compute_instance_update_spec", "compute_disk_spec", "compute_disk_update_spec", "compute_filesystem_spec", "compute_filesystem_update_spec"]
    COMPUTE_INSTANCE_SPEC_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_INSTANCE_UPDATE_SPEC_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_DISK_SPEC_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_DISK_UPDATE_SPEC_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_FILESYSTEM_SPEC_FIELD_NUMBER: _ClassVar[int]
    COMPUTE_FILESYSTEM_UPDATE_SPEC_FIELD_NUMBER: _ClassVar[int]
    compute_instance_spec: _instance_service_pb2.CreateInstanceRequest
    compute_instance_update_spec: _instance_service_pb2.UpdateInstanceRequest
    compute_disk_spec: _disk_service_pb2.CreateDiskRequest
    compute_disk_update_spec: _disk_service_pb2.UpdateDiskRequest
    compute_filesystem_spec: _filesystem_service_pb2.CreateFilesystemRequest
    compute_filesystem_update_spec: _filesystem_service_pb2.UpdateFilesystemRequest
    def __init__(self, compute_instance_spec: _Optional[_Union[_instance_service_pb2.CreateInstanceRequest, _Mapping]] = ..., compute_instance_update_spec: _Optional[_Union[_instance_service_pb2.UpdateInstanceRequest, _Mapping]] = ..., compute_disk_spec: _Optional[_Union[_disk_service_pb2.CreateDiskRequest, _Mapping]] = ..., compute_disk_update_spec: _Optional[_Union[_disk_service_pb2.UpdateDiskRequest, _Mapping]] = ..., compute_filesystem_spec: _Optional[_Union[_filesystem_service_pb2.CreateFilesystemRequest, _Mapping]] = ..., compute_filesystem_update_spec: _Optional[_Union[_filesystem_service_pb2.UpdateFilesystemRequest, _Mapping]] = ...) -> None: ...

class ResourceGroupCost(_message.Message):
    __slots__ = ["general"]
    GENERAL_FIELD_NUMBER: _ClassVar[int]
    general: GeneralTotalCost
    def __init__(self, general: _Optional[_Union[GeneralTotalCost, _Mapping]] = ...) -> None: ...

class GeneralTotalCost(_message.Message):
    __slots__ = ["total"]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    total: CostBreakdown
    def __init__(self, total: _Optional[_Union[CostBreakdown, _Mapping]] = ...) -> None: ...

class GeneralResourceCost(_message.Message):
    __slots__ = ["total"]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    total: CostBreakdown
    def __init__(self, total: _Optional[_Union[CostBreakdown, _Mapping]] = ...) -> None: ...

class CostBreakdown(_message.Message):
    __slots__ = ["cost", "cost_rounded"]
    COST_FIELD_NUMBER: _ClassVar[int]
    COST_ROUNDED_FIELD_NUMBER: _ClassVar[int]
    cost: str
    cost_rounded: str
    def __init__(self, cost: _Optional[str] = ..., cost_rounded: _Optional[str] = ...) -> None: ...
