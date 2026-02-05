from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Warnings(_message.Message):
    __slots__ = ["warnings"]
    WARNINGS_FIELD_NUMBER: _ClassVar[int]
    warnings: _containers.RepeatedCompositeFieldContainer[Warning]
    def __init__(self, warnings: _Optional[_Iterable[_Union[Warning, _Mapping]]] = ...) -> None: ...

class Warning(_message.Message):
    __slots__ = ["target", "code", "summary", "summary_fallback", "details", "details_fallback", "path"]
    class Target(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        TARGET_UNSPECIFIED: _ClassVar[Warning.Target]
        TARGET_CLI: _ClassVar[Warning.Target]
        TARGET_TF: _ClassVar[Warning.Target]
        TARGET_CONSOLE: _ClassVar[Warning.Target]
    TARGET_UNSPECIFIED: Warning.Target
    TARGET_CLI: Warning.Target
    TARGET_TF: Warning.Target
    TARGET_CONSOLE: Warning.Target
    class Code(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        CODE_UNSPECIFIED: _ClassVar[Warning.Code]
        CODE_REGION_ROUTING_FAILOVER: _ClassVar[Warning.Code]
        CODE_DEPRECATED_TOOL_VERSION: _ClassVar[Warning.Code]
        CODE_DEPRECATED_ENDPOINT: _ClassVar[Warning.Code]
        CODE_DEPRECATED_PROTO: _ClassVar[Warning.Code]
        CODE_DEPRECATED_SPEC_VALUE_REQUEST: _ClassVar[Warning.Code]
        CODE_DEPRECATED_SPEC_VALUE_RESPONSE: _ClassVar[Warning.Code]
    CODE_UNSPECIFIED: Warning.Code
    CODE_REGION_ROUTING_FAILOVER: Warning.Code
    CODE_DEPRECATED_TOOL_VERSION: Warning.Code
    CODE_DEPRECATED_ENDPOINT: Warning.Code
    CODE_DEPRECATED_PROTO: Warning.Code
    CODE_DEPRECATED_SPEC_VALUE_REQUEST: Warning.Code
    CODE_DEPRECATED_SPEC_VALUE_RESPONSE: Warning.Code
    TARGET_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FALLBACK_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FALLBACK_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    target: Warning.Target
    code: Warning.Code
    summary: str
    summary_fallback: str
    details: str
    details_fallback: str
    path: str
    def __init__(self, target: _Optional[_Union[Warning.Target, str]] = ..., code: _Optional[_Union[Warning.Code, str]] = ..., summary: _Optional[str] = ..., summary_fallback: _Optional[str] = ..., details: _Optional[str] = ..., details_fallback: _Optional[str] = ..., path: _Optional[str] = ...) -> None: ...
