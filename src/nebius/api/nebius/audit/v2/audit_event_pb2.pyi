from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius.audit.v2 import authentication_pb2 as _authentication_pb2
from nebius.api.nebius.audit.v2 import authorization_pb2 as _authorization_pb2
from nebius.api.nebius.audit.v2 import region_pb2 as _region_pb2
from nebius.api.nebius.audit.v2 import request_pb2 as _request_pb2
from nebius.api.nebius.audit.v2 import resource_pb2 as _resource_pb2
from nebius.api.nebius.audit.v2 import response_pb2 as _response_pb2
from nebius.api.nebius.audit.v2 import service_pb2 as _service_pb2
from nebius.api.nebius.audit.v2 import status_pb2 as _status_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AuditEvent(_message.Message):
    __slots__ = ["id", "source", "spec_version", "type", "service", "action", "time", "event_version", "authentication", "authorization", "resource", "request", "response", "status", "project_region"]
    ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    SPEC_VERSION_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SERVICE_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    EVENT_VERSION_FIELD_NUMBER: _ClassVar[int]
    AUTHENTICATION_FIELD_NUMBER: _ClassVar[int]
    AUTHORIZATION_FIELD_NUMBER: _ClassVar[int]
    RESOURCE_FIELD_NUMBER: _ClassVar[int]
    REQUEST_FIELD_NUMBER: _ClassVar[int]
    RESPONSE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    PROJECT_REGION_FIELD_NUMBER: _ClassVar[int]
    id: str
    source: str
    spec_version: str
    type: str
    service: _service_pb2.Service
    action: str
    time: _timestamp_pb2.Timestamp
    event_version: str
    authentication: _authentication_pb2.Authentication
    authorization: _authorization_pb2.Authorization
    resource: _resource_pb2.Resource
    request: _request_pb2.Request
    response: _response_pb2.Response
    status: _status_pb2.Status
    project_region: _region_pb2.Region
    def __init__(self, id: _Optional[str] = ..., source: _Optional[str] = ..., spec_version: _Optional[str] = ..., type: _Optional[str] = ..., service: _Optional[_Union[_service_pb2.Service, _Mapping]] = ..., action: _Optional[str] = ..., time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., event_version: _Optional[str] = ..., authentication: _Optional[_Union[_authentication_pb2.Authentication, _Mapping]] = ..., authorization: _Optional[_Union[_authorization_pb2.Authorization, _Mapping]] = ..., resource: _Optional[_Union[_resource_pb2.Resource, _Mapping]] = ..., request: _Optional[_Union[_request_pb2.Request, _Mapping]] = ..., response: _Optional[_Union[_response_pb2.Response, _Mapping]] = ..., status: _Optional[_Union[_status_pb2.Status, str]] = ..., project_region: _Optional[_Union[_region_pb2.Region, _Mapping]] = ...) -> None: ...
