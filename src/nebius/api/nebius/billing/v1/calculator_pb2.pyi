from google.protobuf import any_pb2 as _any_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ResourceSpec(_message.Message):
    __slots__ = ["spec"]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    spec: _any_pb2.Any
    def __init__(self, spec: _Optional[_Union[_any_pb2.Any, _Mapping]] = ...) -> None: ...

class GeneralTotalCost(_message.Message):
    __slots__ = ["total"]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    total: CostBreakdown
    def __init__(self, total: _Optional[_Union[CostBreakdown, _Mapping]] = ...) -> None: ...

class RangeTotalCost(_message.Message):
    __slots__ = ["min", "max"]
    MIN_FIELD_NUMBER: _ClassVar[int]
    MAX_FIELD_NUMBER: _ClassVar[int]
    min: CostBreakdown
    max: CostBreakdown
    def __init__(self, min: _Optional[_Union[CostBreakdown, _Mapping]] = ..., max: _Optional[_Union[CostBreakdown, _Mapping]] = ...) -> None: ...

class ResourceCost(_message.Message):
    __slots__ = ["metadata", "override_metadata", "aggregation_unit", "general", "fixed_instance", "autoscale"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    OVERRIDE_METADATA_FIELD_NUMBER: _ClassVar[int]
    AGGREGATION_UNIT_FIELD_NUMBER: _ClassVar[int]
    GENERAL_FIELD_NUMBER: _ClassVar[int]
    FIXED_INSTANCE_FIELD_NUMBER: _ClassVar[int]
    AUTOSCALE_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    override_metadata: _metadata_pb2.ResourceMetadata
    aggregation_unit: AggregationUnit
    general: GeneralResourceCost
    fixed_instance: FixedInstanceResourceCost
    autoscale: AutoscaleResourceCost
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., override_metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., aggregation_unit: _Optional[_Union[AggregationUnit, _Mapping]] = ..., general: _Optional[_Union[GeneralResourceCost, _Mapping]] = ..., fixed_instance: _Optional[_Union[FixedInstanceResourceCost, _Mapping]] = ..., autoscale: _Optional[_Union[AutoscaleResourceCost, _Mapping]] = ...) -> None: ...

class GeneralResourceCost(_message.Message):
    __slots__ = ["total"]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    total: CostBreakdown
    def __init__(self, total: _Optional[_Union[CostBreakdown, _Mapping]] = ...) -> None: ...

class FixedInstanceResourceCost(_message.Message):
    __slots__ = ["total", "per_instance", "instance_count"]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    PER_INSTANCE_FIELD_NUMBER: _ClassVar[int]
    INSTANCE_COUNT_FIELD_NUMBER: _ClassVar[int]
    total: CostBreakdown
    per_instance: CostBreakdown
    instance_count: int
    def __init__(self, total: _Optional[_Union[CostBreakdown, _Mapping]] = ..., per_instance: _Optional[_Union[CostBreakdown, _Mapping]] = ..., instance_count: _Optional[int] = ...) -> None: ...

class AutoscaleResourceCost(_message.Message):
    __slots__ = ["min_cost", "max_cost", "per_instance", "min_instances", "max_instances"]
    MIN_COST_FIELD_NUMBER: _ClassVar[int]
    MAX_COST_FIELD_NUMBER: _ClassVar[int]
    PER_INSTANCE_FIELD_NUMBER: _ClassVar[int]
    MIN_INSTANCES_FIELD_NUMBER: _ClassVar[int]
    MAX_INSTANCES_FIELD_NUMBER: _ClassVar[int]
    min_cost: CostBreakdown
    max_cost: CostBreakdown
    per_instance: CostBreakdown
    min_instances: int
    max_instances: int
    def __init__(self, min_cost: _Optional[_Union[CostBreakdown, _Mapping]] = ..., max_cost: _Optional[_Union[CostBreakdown, _Mapping]] = ..., per_instance: _Optional[_Union[CostBreakdown, _Mapping]] = ..., min_instances: _Optional[int] = ..., max_instances: _Optional[int] = ...) -> None: ...

class CostBreakdown(_message.Message):
    __slots__ = ["sku_costs", "cost", "cost_rounded"]
    SKU_COSTS_FIELD_NUMBER: _ClassVar[int]
    COST_FIELD_NUMBER: _ClassVar[int]
    COST_ROUNDED_FIELD_NUMBER: _ClassVar[int]
    sku_costs: _containers.RepeatedCompositeFieldContainer[SkuCost]
    cost: str
    cost_rounded: str
    def __init__(self, sku_costs: _Optional[_Iterable[_Union[SkuCost, _Mapping]]] = ..., cost: _Optional[str] = ..., cost_rounded: _Optional[str] = ...) -> None: ...

class SkuCost(_message.Message):
    __slots__ = ["sku_id", "quantity", "quantity_rounded", "cost", "cost_rounded"]
    SKU_ID_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_ROUNDED_FIELD_NUMBER: _ClassVar[int]
    COST_FIELD_NUMBER: _ClassVar[int]
    COST_ROUNDED_FIELD_NUMBER: _ClassVar[int]
    sku_id: str
    quantity: str
    quantity_rounded: str
    cost: str
    cost_rounded: str
    def __init__(self, sku_id: _Optional[str] = ..., quantity: _Optional[str] = ..., quantity_rounded: _Optional[str] = ..., cost: _Optional[str] = ..., cost_rounded: _Optional[str] = ...) -> None: ...

class TotalCost(_message.Message):
    __slots__ = ["aggregation_unit", "general", "range"]
    AGGREGATION_UNIT_FIELD_NUMBER: _ClassVar[int]
    GENERAL_FIELD_NUMBER: _ClassVar[int]
    RANGE_FIELD_NUMBER: _ClassVar[int]
    aggregation_unit: AggregationUnit
    general: GeneralResourceCost
    range: RangeTotalCost
    def __init__(self, aggregation_unit: _Optional[_Union[AggregationUnit, _Mapping]] = ..., general: _Optional[_Union[GeneralResourceCost, _Mapping]] = ..., range: _Optional[_Union[RangeTotalCost, _Mapping]] = ...) -> None: ...

class FilterAggregationUnit(_message.Message):
    __slots__ = ["filter_aggregation_unit_values"]
    class FilterAggregationUnitValue(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        FILTER_AGGREGATION_UNIT_UNSPECIFIED: _ClassVar[FilterAggregationUnit.FilterAggregationUnitValue]
        FILTER_AGGREGATION_UNIT_MINUTE: _ClassVar[FilterAggregationUnit.FilterAggregationUnitValue]
        FILTER_AGGREGATION_UNIT_HOUR: _ClassVar[FilterAggregationUnit.FilterAggregationUnitValue]
        FILTER_AGGREGATION_UNIT_DAY: _ClassVar[FilterAggregationUnit.FilterAggregationUnitValue]
        FILTER_AGGREGATION_UNIT_WEEK: _ClassVar[FilterAggregationUnit.FilterAggregationUnitValue]
        FILTER_AGGREGATION_UNIT_MONTH: _ClassVar[FilterAggregationUnit.FilterAggregationUnitValue]
    FILTER_AGGREGATION_UNIT_UNSPECIFIED: FilterAggregationUnit.FilterAggregationUnitValue
    FILTER_AGGREGATION_UNIT_MINUTE: FilterAggregationUnit.FilterAggregationUnitValue
    FILTER_AGGREGATION_UNIT_HOUR: FilterAggregationUnit.FilterAggregationUnitValue
    FILTER_AGGREGATION_UNIT_DAY: FilterAggregationUnit.FilterAggregationUnitValue
    FILTER_AGGREGATION_UNIT_WEEK: FilterAggregationUnit.FilterAggregationUnitValue
    FILTER_AGGREGATION_UNIT_MONTH: FilterAggregationUnit.FilterAggregationUnitValue
    FILTER_AGGREGATION_UNIT_VALUES_FIELD_NUMBER: _ClassVar[int]
    filter_aggregation_unit_values: _containers.RepeatedScalarFieldContainer[FilterAggregationUnit.FilterAggregationUnitValue]
    def __init__(self, filter_aggregation_unit_values: _Optional[_Iterable[_Union[FilterAggregationUnit.FilterAggregationUnitValue, str]]] = ...) -> None: ...

class AggregationUnit(_message.Message):
    __slots__ = ["unit", "unit_type"]
    class UnitType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        UNIT_TYPE_UNSPECIFIED: _ClassVar[AggregationUnit.UnitType]
        UNIT_TYPE_TIME_BASED: _ClassVar[AggregationUnit.UnitType]
        UNIT_TYPE_USAGE_BASED: _ClassVar[AggregationUnit.UnitType]
    UNIT_TYPE_UNSPECIFIED: AggregationUnit.UnitType
    UNIT_TYPE_TIME_BASED: AggregationUnit.UnitType
    UNIT_TYPE_USAGE_BASED: AggregationUnit.UnitType
    UNIT_FIELD_NUMBER: _ClassVar[int]
    UNIT_TYPE_FIELD_NUMBER: _ClassVar[int]
    unit: str
    unit_type: AggregationUnit.UnitType
    def __init__(self, unit: _Optional[str] = ..., unit_type: _Optional[_Union[AggregationUnit.UnitType, str]] = ...) -> None: ...
