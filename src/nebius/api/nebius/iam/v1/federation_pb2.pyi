from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Federation(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: FederationSpec
    status: FederationStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[FederationSpec, _Mapping]] = ..., status: _Optional[_Union[FederationStatus, _Mapping]] = ...) -> None: ...

class FederationSpec(_message.Message):
    __slots__ = ["user_account_auto_creation", "active", "saml_settings"]
    USER_ACCOUNT_AUTO_CREATION_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_FIELD_NUMBER: _ClassVar[int]
    SAML_SETTINGS_FIELD_NUMBER: _ClassVar[int]
    user_account_auto_creation: bool
    active: bool
    saml_settings: SamlSettings
    def __init__(self, user_account_auto_creation: bool = ..., active: bool = ..., saml_settings: _Optional[_Union[SamlSettings, _Mapping]] = ...) -> None: ...

class SamlSettings(_message.Message):
    __slots__ = ["idp_issuer", "sso_url", "force_authn"]
    IDP_ISSUER_FIELD_NUMBER: _ClassVar[int]
    SSO_URL_FIELD_NUMBER: _ClassVar[int]
    FORCE_AUTHN_FIELD_NUMBER: _ClassVar[int]
    idp_issuer: str
    sso_url: str
    force_authn: bool
    def __init__(self, idp_issuer: _Optional[str] = ..., sso_url: _Optional[str] = ..., force_authn: bool = ...) -> None: ...

class FederationStatus(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...
