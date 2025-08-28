from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Request(_message.Message):
    __slots__ = ["client_ip", "user_agent", "request_id", "parameters", "idempotency_id", "trace_id", "ja3_fingerprint"]
    CLIENT_IP_FIELD_NUMBER: _ClassVar[int]
    USER_AGENT_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    PARAMETERS_FIELD_NUMBER: _ClassVar[int]
    IDEMPOTENCY_ID_FIELD_NUMBER: _ClassVar[int]
    TRACE_ID_FIELD_NUMBER: _ClassVar[int]
    JA3_FINGERPRINT_FIELD_NUMBER: _ClassVar[int]
    client_ip: str
    user_agent: str
    request_id: str
    parameters: _struct_pb2.Struct
    idempotency_id: str
    trace_id: str
    ja3_fingerprint: str
    def __init__(self, client_ip: _Optional[str] = ..., user_agent: _Optional[str] = ..., request_id: _Optional[str] = ..., parameters: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., idempotency_id: _Optional[str] = ..., trace_id: _Optional[str] = ..., ja3_fingerprint: _Optional[str] = ...) -> None: ...
