from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RuleDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    DIRECTION_UNSPECIFIED: _ClassVar[RuleDirection]
    INGRESS: _ClassVar[RuleDirection]
    EGRESS: _ClassVar[RuleDirection]

class RuleProtocol(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    PROTOCOL_UNSPECIFIED: _ClassVar[RuleProtocol]
    ANY: _ClassVar[RuleProtocol]
    TCP: _ClassVar[RuleProtocol]
    UDP: _ClassVar[RuleProtocol]
    ICMP: _ClassVar[RuleProtocol]

class RuleAccessAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    ACCESS_UNSPECIFIED: _ClassVar[RuleAccessAction]
    ALLOW: _ClassVar[RuleAccessAction]
    DENY: _ClassVar[RuleAccessAction]

class RuleType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    RULE_TYPE_UNSPECIFIED: _ClassVar[RuleType]
    STATEFUL: _ClassVar[RuleType]
    STATELESS: _ClassVar[RuleType]
DIRECTION_UNSPECIFIED: RuleDirection
INGRESS: RuleDirection
EGRESS: RuleDirection
PROTOCOL_UNSPECIFIED: RuleProtocol
ANY: RuleProtocol
TCP: RuleProtocol
UDP: RuleProtocol
ICMP: RuleProtocol
ACCESS_UNSPECIFIED: RuleAccessAction
ALLOW: RuleAccessAction
DENY: RuleAccessAction
RULE_TYPE_UNSPECIFIED: RuleType
STATEFUL: RuleType
STATELESS: RuleType

class SecurityRule(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: SecurityRuleSpec
    status: SecurityRuleStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[SecurityRuleSpec, _Mapping]] = ..., status: _Optional[_Union[SecurityRuleStatus, _Mapping]] = ...) -> None: ...

class SecurityRuleSpec(_message.Message):
    __slots__ = ["access", "priority", "protocol", "ingress", "egress", "type"]
    ACCESS_FIELD_NUMBER: _ClassVar[int]
    PRIORITY_FIELD_NUMBER: _ClassVar[int]
    PROTOCOL_FIELD_NUMBER: _ClassVar[int]
    INGRESS_FIELD_NUMBER: _ClassVar[int]
    EGRESS_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    access: RuleAccessAction
    priority: int
    protocol: RuleProtocol
    ingress: RuleIngress
    egress: RuleEgress
    type: RuleType
    def __init__(self, access: _Optional[_Union[RuleAccessAction, str]] = ..., priority: _Optional[int] = ..., protocol: _Optional[_Union[RuleProtocol, str]] = ..., ingress: _Optional[_Union[RuleIngress, _Mapping]] = ..., egress: _Optional[_Union[RuleEgress, _Mapping]] = ..., type: _Optional[_Union[RuleType, str]] = ...) -> None: ...

class RuleIngress(_message.Message):
    __slots__ = ["source_security_group_id", "source_cidrs", "destination_ports"]
    SOURCE_SECURITY_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_CIDRS_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_PORTS_FIELD_NUMBER: _ClassVar[int]
    source_security_group_id: str
    source_cidrs: _containers.RepeatedScalarFieldContainer[str]
    destination_ports: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, source_security_group_id: _Optional[str] = ..., source_cidrs: _Optional[_Iterable[str]] = ..., destination_ports: _Optional[_Iterable[int]] = ...) -> None: ...

class RuleEgress(_message.Message):
    __slots__ = ["destination_security_group_id", "destination_cidrs", "destination_ports"]
    DESTINATION_SECURITY_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_CIDRS_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_PORTS_FIELD_NUMBER: _ClassVar[int]
    destination_security_group_id: str
    destination_cidrs: _containers.RepeatedScalarFieldContainer[str]
    destination_ports: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, destination_security_group_id: _Optional[str] = ..., destination_cidrs: _Optional[_Iterable[str]] = ..., destination_ports: _Optional[_Iterable[int]] = ...) -> None: ...

class SecurityRuleStatus(_message.Message):
    __slots__ = ["state", "effective_priority", "direction", "source", "destination"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[SecurityRuleStatus.State]
        CREATING: _ClassVar[SecurityRuleStatus.State]
        READY: _ClassVar[SecurityRuleStatus.State]
        DELETING: _ClassVar[SecurityRuleStatus.State]
    STATE_UNSPECIFIED: SecurityRuleStatus.State
    CREATING: SecurityRuleStatus.State
    READY: SecurityRuleStatus.State
    DELETING: SecurityRuleStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_PRIORITY_FIELD_NUMBER: _ClassVar[int]
    DIRECTION_FIELD_NUMBER: _ClassVar[int]
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    state: SecurityRuleStatus.State
    effective_priority: int
    direction: RuleDirection
    source: RuleMatchStatus
    destination: RuleMatchStatus
    def __init__(self, state: _Optional[_Union[SecurityRuleStatus.State, str]] = ..., effective_priority: _Optional[int] = ..., direction: _Optional[_Union[RuleDirection, str]] = ..., source: _Optional[_Union[RuleMatchStatus, _Mapping]] = ..., destination: _Optional[_Union[RuleMatchStatus, _Mapping]] = ...) -> None: ...

class RuleMatchStatus(_message.Message):
    __slots__ = ["security_group_id", "cidrs", "ports"]
    SECURITY_GROUP_ID_FIELD_NUMBER: _ClassVar[int]
    CIDRS_FIELD_NUMBER: _ClassVar[int]
    PORTS_FIELD_NUMBER: _ClassVar[int]
    security_group_id: str
    cidrs: _containers.RepeatedScalarFieldContainer[str]
    ports: _containers.RepeatedScalarFieldContainer[int]
    def __init__(self, security_group_id: _Optional[str] = ..., cidrs: _Optional[_Iterable[str]] = ..., ports: _Optional[_Iterable[int]] = ...) -> None: ...
