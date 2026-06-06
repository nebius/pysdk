from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.billing.v1 import calculator_pb2 as _calculator_pb2
from nebius.api.nebius.billing.v1 import offer_type_pb2 as _offer_type_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EstimateBatchRequest(_message.Message):
    __slots__ = ["resource_specs", "offer_types", "currency", "filter_aggregation_unit"]
    RESOURCE_SPECS_FIELD_NUMBER: _ClassVar[int]
    OFFER_TYPES_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    FILTER_AGGREGATION_UNIT_FIELD_NUMBER: _ClassVar[int]
    resource_specs: _containers.RepeatedCompositeFieldContainer[_calculator_pb2.ResourceSpec]
    offer_types: _containers.RepeatedScalarFieldContainer[_offer_type_pb2.OfferType]
    currency: str
    filter_aggregation_unit: _calculator_pb2.FilterAggregationUnit
    def __init__(self, resource_specs: _Optional[_Iterable[_Union[_calculator_pb2.ResourceSpec, _Mapping]]] = ..., offer_types: _Optional[_Iterable[_Union[_offer_type_pb2.OfferType, str]]] = ..., currency: _Optional[str] = ..., filter_aggregation_unit: _Optional[_Union[_calculator_pb2.FilterAggregationUnit, _Mapping]] = ...) -> None: ...

class EstimateBatchResponse(_message.Message):
    __slots__ = ["resource_costs", "total_costs", "currency"]
    RESOURCE_COSTS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_COSTS_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    resource_costs: _containers.RepeatedCompositeFieldContainer[_calculator_pb2.ResourceCost]
    total_costs: _containers.RepeatedCompositeFieldContainer[_calculator_pb2.TotalCost]
    currency: str
    def __init__(self, resource_costs: _Optional[_Iterable[_Union[_calculator_pb2.ResourceCost, _Mapping]]] = ..., total_costs: _Optional[_Iterable[_Union[_calculator_pb2.TotalCost, _Mapping]]] = ..., currency: _Optional[str] = ...) -> None: ...
