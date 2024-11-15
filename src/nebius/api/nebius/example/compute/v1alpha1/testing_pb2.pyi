from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import any_pb2 as _any_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Recursive(_message.Message):
    __slots__ = ("str", "recursion")
    STR_FIELD_NUMBER: _ClassVar[int]
    RECURSION_FIELD_NUMBER: _ClassVar[int]
    str: str
    recursion: Recursive
    def __init__(self, str: _Optional[str] = ..., recursion: _Optional[_Union[Recursive, _Mapping]] = ...) -> None: ...

class TestingSpec(_message.Message):
    __slots__ = ("any", "duration", "timestamp", "recursive", "any_out", "duration_out", "timestamp_out", "recursive_out", "non_empty_default", "test_tf_validators", "sensitive_input_only", "dur", "time", "duration_array", "optional_well_known", "optional_message", "sio_repeated", "sio_map", "sio_obj")
    class SioMapEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    ANY_FIELD_NUMBER: _ClassVar[int]
    DURATION_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    RECURSIVE_FIELD_NUMBER: _ClassVar[int]
    ANY_OUT_FIELD_NUMBER: _ClassVar[int]
    DURATION_OUT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_OUT_FIELD_NUMBER: _ClassVar[int]
    RECURSIVE_OUT_FIELD_NUMBER: _ClassVar[int]
    NON_EMPTY_DEFAULT_FIELD_NUMBER: _ClassVar[int]
    TEST_TF_VALIDATORS_FIELD_NUMBER: _ClassVar[int]
    SENSITIVE_INPUT_ONLY_FIELD_NUMBER: _ClassVar[int]
    DUR_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    DURATION_ARRAY_FIELD_NUMBER: _ClassVar[int]
    OPTIONAL_WELL_KNOWN_FIELD_NUMBER: _ClassVar[int]
    OPTIONAL_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SIO_REPEATED_FIELD_NUMBER: _ClassVar[int]
    SIO_MAP_FIELD_NUMBER: _ClassVar[int]
    SIO_OBJ_FIELD_NUMBER: _ClassVar[int]
    any: _any_pb2.Any
    duration: _duration_pb2.Duration
    timestamp: _timestamp_pb2.Timestamp
    recursive: Recursive
    any_out: _any_pb2.Any
    duration_out: _duration_pb2.Duration
    timestamp_out: _timestamp_pb2.Timestamp
    recursive_out: Recursive
    non_empty_default: str
    test_tf_validators: TestTFValidators
    sensitive_input_only: str
    dur: _duration_pb2.Duration
    time: _timestamp_pb2.Timestamp
    duration_array: _containers.RepeatedCompositeFieldContainer[_duration_pb2.Duration]
    optional_well_known: _timestamp_pb2.Timestamp
    optional_message: TestTFProtovalidateOneof
    sio_repeated: _containers.RepeatedScalarFieldContainer[str]
    sio_map: _containers.ScalarMap[str, int]
    sio_obj: TestSimple
    def __init__(self, any: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., duration: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., recursive: _Optional[_Union[Recursive, _Mapping]] = ..., any_out: _Optional[_Union[_any_pb2.Any, _Mapping]] = ..., duration_out: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., timestamp_out: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., recursive_out: _Optional[_Union[Recursive, _Mapping]] = ..., non_empty_default: _Optional[str] = ..., test_tf_validators: _Optional[_Union[TestTFValidators, _Mapping]] = ..., sensitive_input_only: _Optional[str] = ..., dur: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., duration_array: _Optional[_Iterable[_Union[_duration_pb2.Duration, _Mapping]]] = ..., optional_well_known: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., optional_message: _Optional[_Union[TestTFProtovalidateOneof, _Mapping]] = ..., sio_repeated: _Optional[_Iterable[str]] = ..., sio_map: _Optional[_Mapping[str, int]] = ..., sio_obj: _Optional[_Union[TestSimple, _Mapping]] = ...) -> None: ...

class TestSimple(_message.Message):
    __slots__ = ("a",)
    A_FIELD_NUMBER: _ClassVar[int]
    a: int
    def __init__(self, a: _Optional[int] = ...) -> None: ...

class TestTFValidators(_message.Message):
    __slots__ = ("test_type_limit_validator", "test_protovalidate_main", "a", "b", "test_message", "test_oneof_requirement")
    TEST_TYPE_LIMIT_VALIDATOR_FIELD_NUMBER: _ClassVar[int]
    TEST_PROTOVALIDATE_MAIN_FIELD_NUMBER: _ClassVar[int]
    A_FIELD_NUMBER: _ClassVar[int]
    B_FIELD_NUMBER: _ClassVar[int]
    TEST_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TEST_ONEOF_REQUIREMENT_FIELD_NUMBER: _ClassVar[int]
    test_type_limit_validator: int
    test_protovalidate_main: int
    a: int
    b: int
    test_message: TestTFProtovalidateMessage
    test_oneof_requirement: TestTFProtovalidateOneof
    def __init__(self, test_type_limit_validator: _Optional[int] = ..., test_protovalidate_main: _Optional[int] = ..., a: _Optional[int] = ..., b: _Optional[int] = ..., test_message: _Optional[_Union[TestTFProtovalidateMessage, _Mapping]] = ..., test_oneof_requirement: _Optional[_Union[TestTFProtovalidateOneof, _Mapping]] = ...) -> None: ...

class TestTFProtovalidateMessage(_message.Message):
    __slots__ = ("a", "b")
    A_FIELD_NUMBER: _ClassVar[int]
    B_FIELD_NUMBER: _ClassVar[int]
    a: int
    b: int
    def __init__(self, a: _Optional[int] = ..., b: _Optional[int] = ...) -> None: ...

class TestTFProtovalidateOneof(_message.Message):
    __slots__ = ("a", "b")
    A_FIELD_NUMBER: _ClassVar[int]
    B_FIELD_NUMBER: _ClassVar[int]
    a: int
    b: int
    def __init__(self, a: _Optional[int] = ..., b: _Optional[int] = ...) -> None: ...
