from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PresetSpec(_message.Message):
    __slots__ = ["hosts", "disk", "resources"]
    HOSTS_FIELD_NUMBER: _ClassVar[int]
    DISK_FIELD_NUMBER: _ClassVar[int]
    RESOURCES_FIELD_NUMBER: _ClassVar[int]
    hosts: _template_pb2.HostSpec
    disk: _template_pb2.DiskSpec
    resources: _template_pb2.ResourcesSpec
    def __init__(self, hosts: _Optional[_Union[_template_pb2.HostSpec, _Mapping]] = ..., disk: _Optional[_Union[_template_pb2.DiskSpec, _Mapping]] = ..., resources: _Optional[_Union[_template_pb2.ResourcesSpec, _Mapping]] = ...) -> None: ...
