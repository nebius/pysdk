from google.protobuf import descriptor_pb2 as _descriptor_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    RESOURCE_BEHAVIOR_UNSPECIFIED: _ClassVar[ResourceBehavior]
    MOVABLE: _ClassVar[ResourceBehavior]
    UNNAMED: _ClassVar[ResourceBehavior]
    IMMUTABLE_NAME: _ClassVar[ResourceBehavior]

class FieldBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    FIELD_BEHAVIOR_UNSPECIFIED: _ClassVar[FieldBehavior]
    IMMUTABLE: _ClassVar[FieldBehavior]
    IDENTIFIER: _ClassVar[FieldBehavior]
    INPUT_ONLY: _ClassVar[FieldBehavior]
    OUTPUT_ONLY: _ClassVar[FieldBehavior]
    MEANINGFUL_EMPTY_VALUE: _ClassVar[FieldBehavior]
    NON_EMPTY_DEFAULT: _ClassVar[FieldBehavior]
RESOURCE_BEHAVIOR_UNSPECIFIED: ResourceBehavior
MOVABLE: ResourceBehavior
UNNAMED: ResourceBehavior
IMMUTABLE_NAME: ResourceBehavior
FIELD_BEHAVIOR_UNSPECIFIED: FieldBehavior
IMMUTABLE: FieldBehavior
IDENTIFIER: FieldBehavior
INPUT_ONLY: FieldBehavior
OUTPUT_ONLY: FieldBehavior
MEANINGFUL_EMPTY_VALUE: FieldBehavior
NON_EMPTY_DEFAULT: FieldBehavior
FILE_DEPRECATION_DETAILS_FIELD_NUMBER: _ClassVar[int]
file_deprecation_details: _descriptor.FieldDescriptor
API_SERVICE_NAME_FIELD_NUMBER: _ClassVar[int]
api_service_name: _descriptor.FieldDescriptor
SERVICE_DEPRECATION_DETAILS_FIELD_NUMBER: _ClassVar[int]
service_deprecation_details: _descriptor.FieldDescriptor
SERVICE_PY_SDK_FIELD_NUMBER: _ClassVar[int]
service_py_sdk: _descriptor.FieldDescriptor
METHOD_DEPRECATION_DETAILS_FIELD_NUMBER: _ClassVar[int]
method_deprecation_details: _descriptor.FieldDescriptor
METHOD_PY_SDK_FIELD_NUMBER: _ClassVar[int]
method_py_sdk: _descriptor.FieldDescriptor
SEND_RESET_MASK_FIELD_NUMBER: _ClassVar[int]
send_reset_mask: _descriptor.FieldDescriptor
RESOURCE_BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
resource_behavior: _descriptor.FieldDescriptor
MESSAGE_DEPRECATION_DETAILS_FIELD_NUMBER: _ClassVar[int]
message_deprecation_details: _descriptor.FieldDescriptor
MESSAGE_PY_SDK_FIELD_NUMBER: _ClassVar[int]
message_py_sdk: _descriptor.FieldDescriptor
FIELD_BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
field_behavior: _descriptor.FieldDescriptor
SENSITIVE_FIELD_NUMBER: _ClassVar[int]
sensitive: _descriptor.FieldDescriptor
CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
credentials: _descriptor.FieldDescriptor
FIELD_DEPRECATION_DETAILS_FIELD_NUMBER: _ClassVar[int]
field_deprecation_details: _descriptor.FieldDescriptor
FIELD_PY_SDK_FIELD_NUMBER: _ClassVar[int]
field_py_sdk: _descriptor.FieldDescriptor
NID_FIELD_NUMBER: _ClassVar[int]
nid: _descriptor.FieldDescriptor
ONEOF_BEHAVIOR_FIELD_NUMBER: _ClassVar[int]
oneof_behavior: _descriptor.FieldDescriptor
ONEOF_PY_SDK_FIELD_NUMBER: _ClassVar[int]
oneof_py_sdk: _descriptor.FieldDescriptor
ENUM_PY_SDK_FIELD_NUMBER: _ClassVar[int]
enum_py_sdk: _descriptor.FieldDescriptor
ENUM_DEPRECATION_DETAILS_FIELD_NUMBER: _ClassVar[int]
enum_deprecation_details: _descriptor.FieldDescriptor
ENUM_VALUE_DEPRECATION_DETAILS_FIELD_NUMBER: _ClassVar[int]
enum_value_deprecation_details: _descriptor.FieldDescriptor
ENUM_VALUE_PY_SDK_FIELD_NUMBER: _ClassVar[int]
enum_value_py_sdk: _descriptor.FieldDescriptor

class ServicePySDKSettings(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class MethodPySDKSettings(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class FieldPySDKSettings(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class MessagePySDKSettings(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class OneofPySDKSettings(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class EnumPySDKSettings(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class EnumValuePySDKSettings(_message.Message):
    __slots__ = ["name"]
    NAME_FIELD_NUMBER: _ClassVar[int]
    name: str
    def __init__(self, name: _Optional[str] = ...) -> None: ...

class DeprecationDetails(_message.Message):
    __slots__ = ["effective_at", "description", "description_cli"]
    EFFECTIVE_AT_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_CLI_FIELD_NUMBER: _ClassVar[int]
    effective_at: str
    description: str
    description_cli: str
    def __init__(self, effective_at: _Optional[str] = ..., description: _Optional[str] = ..., description_cli: _Optional[str] = ...) -> None: ...

class NIDFieldSettings(_message.Message):
    __slots__ = ["resource", "parent_resource"]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    PARENT_RESOURCE_FIELD_NUMBER: _ClassVar[int]
    resource: _containers.RepeatedScalarFieldContainer[str]
    parent_resource: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, resource: _Optional[_Iterable[str]] = ..., parent_resource: _Optional[_Iterable[str]] = ...) -> None: ...
