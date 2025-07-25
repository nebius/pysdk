from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class NetworkInterfaceSpec(_message.Message):
    __slots__ = ["subnet_id", "name", "ip_address", "public_ip_address"]
    SUBNET_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    subnet_id: str
    name: str
    ip_address: IPAddress
    public_ip_address: PublicIPAddress
    def __init__(self, subnet_id: _Optional[str] = ..., name: _Optional[str] = ..., ip_address: _Optional[_Union[IPAddress, _Mapping]] = ..., public_ip_address: _Optional[_Union[PublicIPAddress, _Mapping]] = ...) -> None: ...

class IPAddress(_message.Message):
    __slots__ = ["allocation_id"]
    ALLOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    allocation_id: str
    def __init__(self, allocation_id: _Optional[str] = ...) -> None: ...

class PublicIPAddress(_message.Message):
    __slots__ = ["allocation_id", "static"]
    ALLOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    STATIC_FIELD_NUMBER: _ClassVar[int]
    allocation_id: str
    static: bool
    def __init__(self, allocation_id: _Optional[str] = ..., static: bool = ...) -> None: ...

class NetworkInterfaceStatus(_message.Message):
    __slots__ = ["index", "name", "ip_address", "public_ip_address", "mac_address", "fqdn"]
    INDEX_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    PUBLIC_IP_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    MAC_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    FQDN_FIELD_NUMBER: _ClassVar[int]
    index: int
    name: str
    ip_address: IPAddressStatus
    public_ip_address: PublicIPAddressStatus
    mac_address: str
    fqdn: str
    def __init__(self, index: _Optional[int] = ..., name: _Optional[str] = ..., ip_address: _Optional[_Union[IPAddressStatus, _Mapping]] = ..., public_ip_address: _Optional[_Union[PublicIPAddressStatus, _Mapping]] = ..., mac_address: _Optional[str] = ..., fqdn: _Optional[str] = ...) -> None: ...

class IPAddressStatus(_message.Message):
    __slots__ = ["address", "allocation_id"]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ALLOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    address: str
    allocation_id: str
    def __init__(self, address: _Optional[str] = ..., allocation_id: _Optional[str] = ...) -> None: ...

class PublicIPAddressStatus(_message.Message):
    __slots__ = ["address", "allocation_id", "static"]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    ALLOCATION_ID_FIELD_NUMBER: _ClassVar[int]
    STATIC_FIELD_NUMBER: _ClassVar[int]
    address: str
    allocation_id: str
    static: bool
    def __init__(self, address: _Optional[str] = ..., allocation_id: _Optional[str] = ..., static: bool = ...) -> None: ...
