from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ProgressData(_message.Message):
    __slots__ = ["problems"]
    PROBLEMS_FIELD_NUMBER: _ClassVar[int]
    problems: _containers.RepeatedCompositeFieldContainer[Problem]
    def __init__(self, problems: _Optional[_Iterable[_Union[Problem, _Mapping]]] = ...) -> None: ...

class Problem(_message.Message):
    __slots__ = ["stage", "message"]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    stage: str
    message: str
    def __init__(self, stage: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...
