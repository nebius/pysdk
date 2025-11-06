from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.vpc.v1 import pool_pb2 as _pool_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Allocation(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: AllocationSpec
    status: AllocationStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[AllocationSpec, _Mapping]] = ..., status: _Optional[_Union[AllocationStatus, _Mapping]] = ...) -> None: ...

class AllocationSpec(_message.Message):
    __slots__ = ["ipv4_private", "ipv4_public"]
    IPV4_PRIVATE_FIELD_NUMBER: _ClassVar[int]
    IPV4_PUBLIC_FIELD_NUMBER: _ClassVar[int]
    ipv4_private: IPv4PrivateAllocationSpec
    ipv4_public: IPv4PublicAllocationSpec
    def __init__(self, ipv4_private: _Optional[_Union[IPv4PrivateAllocationSpec, _Mapping]] = ..., ipv4_public: _Optional[_Union[IPv4PublicAllocationSpec, _Mapping]] = ...) -> None: ...

class IPv4PrivateAllocationSpec(_message.Message):
    __slots__ = ["cidr", "subnet_id", "pool_id"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    SUBNET_ID_FIELD_NUMBER: _ClassVar[int]
    POOL_ID_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    subnet_id: str
    pool_id: str
    def __init__(self, cidr: _Optional[str] = ..., subnet_id: _Optional[str] = ..., pool_id: _Optional[str] = ...) -> None: ...

class IPv4PublicAllocationSpec(_message.Message):
    __slots__ = ["cidr", "subnet_id", "pool_id"]
    CIDR_FIELD_NUMBER: _ClassVar[int]
    SUBNET_ID_FIELD_NUMBER: _ClassVar[int]
    POOL_ID_FIELD_NUMBER: _ClassVar[int]
    cidr: str
    subnet_id: str
    pool_id: str
    def __init__(self, cidr: _Optional[str] = ..., subnet_id: _Optional[str] = ..., pool_id: _Optional[str] = ...) -> None: ...

class AllocationStatus(_message.Message):
    __slots__ = ["state", "details", "assignment", "static"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[AllocationStatus.State]
        CREATING: _ClassVar[AllocationStatus.State]
        ALLOCATED: _ClassVar[AllocationStatus.State]
        ASSIGNED: _ClassVar[AllocationStatus.State]
        DELETING: _ClassVar[AllocationStatus.State]
    STATE_UNSPECIFIED: AllocationStatus.State
    CREATING: AllocationStatus.State
    ALLOCATED: AllocationStatus.State
    ASSIGNED: AllocationStatus.State
    DELETING: AllocationStatus.State
    STATE_FIELD_NUMBER: _ClassVar[int]
    DETAILS_FIELD_NUMBER: _ClassVar[int]
    ASSIGNMENT_FIELD_NUMBER: _ClassVar[int]
    STATIC_FIELD_NUMBER: _ClassVar[int]
    state: AllocationStatus.State
    details: AllocationDetails
    assignment: Assignment
    static: bool
    def __init__(self, state: _Optional[_Union[AllocationStatus.State, str]] = ..., details: _Optional[_Union[AllocationDetails, _Mapping]] = ..., assignment: _Optional[_Union[Assignment, _Mapping]] = ..., static: bool = ...) -> None: ...

class AllocationDetails(_message.Message):
    __slots__ = ["allocated_cidr", "pool_id", "version", "subnet_id"]
    ALLOCATED_CIDR_FIELD_NUMBER: _ClassVar[int]
    POOL_ID_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    SUBNET_ID_FIELD_NUMBER: _ClassVar[int]
    allocated_cidr: str
    pool_id: str
    version: _pool_pb2.IpVersion
    subnet_id: str
    def __init__(self, allocated_cidr: _Optional[str] = ..., pool_id: _Optional[str] = ..., version: _Optional[_Union[_pool_pb2.IpVersion, str]] = ..., subnet_id: _Optional[str] = ...) -> None: ...

class Assignment(_message.Message):
    __slots__ = ["network_interface", "load_balancer"]
    NETWORK_INTERFACE_FIELD_NUMBER: _ClassVar[int]
    LOAD_BALANCER_FIELD_NUMBER: _ClassVar[int]
    network_interface: NetworkInterfaceAssignment
    load_balancer: LoadBalancerAssignment
    def __init__(self, network_interface: _Optional[_Union[NetworkInterfaceAssignment, _Mapping]] = ..., load_balancer: _Optional[_Union[LoadBalancerAssignment, _Mapping]] = ...) -> None: ...

class NetworkInterfaceAssignment(_message.Message):
    __slots__ = ["instance_id", "name"]
    INSTANCE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    instance_id: str
    name: str
    def __init__(self, instance_id: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class LoadBalancerAssignment(_message.Message):
    __slots__ = ["id"]
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...
