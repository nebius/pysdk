from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class FederatedCredentials(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: FederatedCredentialsSpec
    status: FederatedCredentialsStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[FederatedCredentialsSpec, _Mapping]] = ..., status: _Optional[_Union[FederatedCredentialsStatus, _Mapping]] = ...) -> None: ...

class FederatedCredentialsSpec(_message.Message):
    __slots__ = ["oidc_provider", "federated_subject_id", "subject_id"]
    OIDC_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    FEDERATED_SUBJECT_ID_FIELD_NUMBER: _ClassVar[int]
    SUBJECT_ID_FIELD_NUMBER: _ClassVar[int]
    oidc_provider: OidcCredentialsProvider
    federated_subject_id: str
    subject_id: str
    def __init__(self, oidc_provider: _Optional[_Union[OidcCredentialsProvider, _Mapping]] = ..., federated_subject_id: _Optional[str] = ..., subject_id: _Optional[str] = ...) -> None: ...

class OidcCredentialsProvider(_message.Message):
    __slots__ = ["issuer_url", "jwk_set_json"]
    ISSUER_URL_FIELD_NUMBER: _ClassVar[int]
    JWK_SET_JSON_FIELD_NUMBER: _ClassVar[int]
    issuer_url: str
    jwk_set_json: str
    def __init__(self, issuer_url: _Optional[str] = ..., jwk_set_json: _Optional[str] = ...) -> None: ...

class FederatedCredentialsStatus(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
