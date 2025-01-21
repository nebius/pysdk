from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class DriverTemplateSpec(_message.Message):
    __slots__ = ["disk", "resources"]
    DISK_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    disk: _template_pb2.DiskSpec
    resources: _template_pb2.ResourcesSpec
    def __init__(self, disk: _Optional[_Union[_template_pb2.DiskSpec, _Mapping]] = ..., resources: _Optional[_Union[_template_pb2.ResourcesSpec, _Mapping]] = ...) -> None: ...

class DynamicAllocationSpec(_message.Message):
    __slots__ = ["min", "max"]
    MIN_FIELD_NUMBER: _ClassVar[int]
    MAX_FIELD_NUMBER: _ClassVar[int]
    min: int
    max: int
    def __init__(self, min: _Optional[int] = ..., max: _Optional[int] = ...) -> None: ...

class ExecutorTemplateSpec(_message.Message):
    __slots__ = ["disk", "resources", "hosts", "hosts_dynamic_allocation"]
    DISK_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    HOSTS_FIELD_NUMBER: _ClassVar[int]
    HOSTS_DYNAMIC_ALLOCATION_FIELD_NUMBER: _ClassVar[int]
    disk: _template_pb2.DiskSpec
    resources: _template_pb2.ResourcesSpec
    hosts: _template_pb2.HostSpec
    hosts_dynamic_allocation: DynamicAllocationSpec
    def __init__(self, disk: _Optional[_Union[_template_pb2.DiskSpec, _Mapping]] = ..., resources: _Optional[_Union[_template_pb2.ResourcesSpec, _Mapping]] = ..., hosts: _Optional[_Union[_template_pb2.HostSpec, _Mapping]] = ..., hosts_dynamic_allocation: _Optional[_Union[DynamicAllocationSpec, _Mapping]] = ...) -> None: ...
