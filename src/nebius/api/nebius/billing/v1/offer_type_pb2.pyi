from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class OfferType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    OFFER_TYPE_UNSPECIFIED: _ClassVar[OfferType]
    OFFER_TYPE_CONTRACT_PRICE: _ClassVar[OfferType]
OFFER_TYPE_UNSPECIFIED: OfferType
OFFER_TYPE_CONTRACT_PRICE: OfferType
