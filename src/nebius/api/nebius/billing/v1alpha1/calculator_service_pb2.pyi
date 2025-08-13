from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.billing.v1alpha1 import calculator_pb2 as _calculator_pb2
from nebius.api.nebius.billing.v1alpha1 import offer_type_pb2 as _offer_type_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EstimateRequest(_message.Message):
    __slots__ = ["resource_spec", "offer_types"]
    RESOURCE_SPEC_FIELD_NUMBER: _ClassVar[int]
    OFFER_TYPES_FIELD_NUMBER: _ClassVar[int]
    resource_spec: _calculator_pb2.ResourceSpec
    offer_types: _containers.RepeatedScalarFieldContainer[_offer_type_pb2.OfferType]
    def __init__(self, resource_spec: _Optional[_Union[_calculator_pb2.ResourceSpec, _Mapping]] = ..., offer_types: _Optional[_Iterable[_Union[_offer_type_pb2.OfferType, str]]] = ...) -> None: ...

class EstimateResponse(_message.Message):
    __slots__ = ["hourly_cost", "monthly_cost"]
    HOURLY_COST_FIELD_NUMBER: _ClassVar[int]
    MONTHLY_COST_FIELD_NUMBER: _ClassVar[int]
    hourly_cost: _calculator_pb2.ResourceGroupCost
    monthly_cost: _calculator_pb2.ResourceGroupCost
    def __init__(self, hourly_cost: _Optional[_Union[_calculator_pb2.ResourceGroupCost, _Mapping]] = ..., monthly_cost: _Optional[_Union[_calculator_pb2.ResourceGroupCost, _Mapping]] = ...) -> None: ...

class EstimateBatchRequest(_message.Message):
    __slots__ = ["resource_specs", "offer_types"]
    RESOURCE_SPECS_FIELD_NUMBER: _ClassVar[int]
    OFFER_TYPES_FIELD_NUMBER: _ClassVar[int]
    resource_specs: _containers.RepeatedCompositeFieldContainer[_calculator_pb2.ResourceSpec]
    offer_types: _containers.RepeatedScalarFieldContainer[_offer_type_pb2.OfferType]
    def __init__(self, resource_specs: _Optional[_Iterable[_Union[_calculator_pb2.ResourceSpec, _Mapping]]] = ..., offer_types: _Optional[_Iterable[_Union[_offer_type_pb2.OfferType, str]]] = ...) -> None: ...

class EstimateBatchResponse(_message.Message):
    __slots__ = ["hourly_cost", "monthly_cost"]
    HOURLY_COST_FIELD_NUMBER: _ClassVar[int]
    MONTHLY_COST_FIELD_NUMBER: _ClassVar[int]
    hourly_cost: _calculator_pb2.ResourceGroupCost
    monthly_cost: _calculator_pb2.ResourceGroupCost
    def __init__(self, hourly_cost: _Optional[_Union[_calculator_pb2.ResourceGroupCost, _Mapping]] = ..., monthly_cost: _Optional[_Union[_calculator_pb2.ResourceGroupCost, _Mapping]] = ...) -> None: ...
