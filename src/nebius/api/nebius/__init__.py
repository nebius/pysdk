# 
# Generated by the nebius.base.protos.compiler.  DO NOT EDIT!
# 

import nebius.base.protos.pb_enum as pb_enum
import nebius.base.protos.descriptor as descriptor
import google.protobuf.descriptor as descriptor_1
import nebius.api.nebius.annotations_pb2 as annotations_pb2
import nebius.base.protos.pb_classes as pb_classes
import google.protobuf.message as message
import collections.abc as abc
import builtins as builtins
import nebius.base.protos.unset as unset
#@ local imports here @#

# file: nebius/annotations.proto
class ResourceBehavior(pb_enum.Enum):
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.EnumDescriptor](".nebius.ResourceBehavior",annotations_pb2.DESCRIPTOR,descriptor_1.EnumDescriptor)
    RESOURCE_BEHAVIOR_UNSPECIFIED = 0
    """
     The behavior of the resource is unspecified.
     Avoid using this default value.
    """
    
    MOVABLE = 1
    """
     Indicates that the resource can be moved to another parent, typically an
     IAM container, though not necessarily limited to this.
     This behavior suggests that the `metadata.parent_id` attribute could be modified.
    """
    
    UNNAMED = 2
    """
     Indicates that the resource name can be unspecified or does not follow
     uniqueness requirement within parent_id and resource type.
    """
    
    IMMUTABLE_NAME = 3
    """
     Indicates that the resource is named, and the name cannot be changed after
     it is created. It is strongly recommended to do srvices with renaming
     capability, as the guidelines suggest.
    """
    

class FieldBehavior(pb_enum.Enum):
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.EnumDescriptor](".nebius.FieldBehavior",annotations_pb2.DESCRIPTOR,descriptor_1.EnumDescriptor)
    FIELD_BEHAVIOR_UNSPECIFIED = 0
    IMMUTABLE = 2
    """
     This indicates that the field can't be changed during a resource update.
     Changing the field value will cause an `INVALID_ARGUMENT` error.
     Resource recreate requires a change of the field value.
    """
    
    IDENTIFIER = 3
    """
     Indicates field is a resource ID, so it MUST be present on a resource
     update, but MUST NOT be set on create.
     Otherwise, RPC will fail with the `INVALID_ARGUMENT` error
    """
    
    INPUT_ONLY = 4
    """
     Indicates field is not present in output.
    """
    
    OUTPUT_ONLY = 5
    """
     Indicates field can't be set on create or changed on update.
     Otherwise, RPC will fail with the `INVALID_ARGUMENT` error
    """
    
    MEANINGFUL_EMPTY_VALUE = 6
    """
     Indicates that an empty message and a null have different semantics.
     Usually, that field is a feature spec message: its empty message enables
     that feature, and null disables it. Such a message is different from `bool`
     because it already has some feature parameters, or they can be added later
     in a backward-compatible way.
     IMPORTANT: if the message itself is recursive, this behavior is forced.
    """
    
    NON_EMPTY_DEFAULT = 7
    """
     Indicates that an empty (default) value will be filled by the server.
     Usually, that field is a feature spec value, which by default is computed.
     Values marked with this annotation won't raise error if they are not set
     and the returned value is not equal to protobuf default.
    
     IMPORTANT:
     Updating this value from explicit to default may not lead to Update call in
     some tools (eg Terraform).
     Compound values (messages, lists and maps) may result in unpredictable
     updates (see examples in guidelines).
    """
    

class RegionRouting(pb_classes.Message):
    __PB2_CLASS__ = annotations_pb2.RegionRouting
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.RegionRouting",annotations_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message.Message|None = None,
        *,
        nid: "abc.Iterable[builtins.str]|None|unset.UnsetType" = unset.Unset,
        disabled: "builtins.bool|None|unset.UnsetType" = unset.Unset,
        strict: "builtins.bool|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(nid, unset.UnsetType):
            self.nid = nid
        if not isinstance(disabled, unset.UnsetType):
            self.disabled = disabled
        if not isinstance(strict, unset.UnsetType):
            self.strict = strict
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "nid",
            "disabled",
            "strict",
        ]
    
    @builtins.property
    def nid(self) -> "abc.MutableSequence[builtins.str]":
        """
         A list of fields to extract the NID from, in order of priority.
         The API Gateway will check each field in sequence and use the first valid NID it finds.
         This overrides the default NID lookup order: `id`, `parent_id`, `metadata.id`, `metadata.parent_id`.
         If the field contains a non-empty list of strings, all NIDs in the array must be valid and have the same routing code.
        """
        
        return super()._get_field("nid", explicit_presence=False,
        wrap=pb_classes.Repeated,
        )
    @nid.setter
    def nid(self, value: "abc.Iterable[builtins.str]|None") -> None:
        return super()._set_field("nid",value,explicit_presence=False,
        )
    
    @builtins.property
    def disabled(self) -> "builtins.bool":
        """
         If true, region routing is disabled for the method.
         When this is set, requests will not be forwarded to a different region, even if an NID is present.
        """
        
        return super()._get_field("disabled", explicit_presence=False,
        )
    @disabled.setter
    def disabled(self, value: "builtins.bool|None") -> None:
        return super()._set_field("disabled",value,explicit_presence=False,
        )
    
    @builtins.property
    def strict(self) -> "builtins.bool":
        """
         In strict mode, the API Gateway returns an INVALID_ARGUMENT error to the user when a routing error occurs,
         rather than forwarding the request to the local region.
        """
        
        return super()._get_field("strict", explicit_presence=False,
        )
    @strict.setter
    def strict(self, value: "builtins.bool|None") -> None:
        return super()._set_field("strict",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "nid":"nid",
        "disabled":"disabled",
        "strict":"strict",
    }
    
class DeprecationDetails(pb_classes.Message):
    __PB2_CLASS__ = annotations_pb2.DeprecationDetails
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.DeprecationDetails",annotations_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message.Message|None = None,
        *,
        effective_at: "builtins.str|None|unset.UnsetType" = unset.Unset,
        description: "builtins.str|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(effective_at, unset.UnsetType):
            self.effective_at = effective_at
        if not isinstance(description, unset.UnsetType):
            self.description = description
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "effective_at",
            "description",
        ]
    
    @builtins.property
    def effective_at(self) -> "builtins.str":
        """
         The date when this method, service, message or field will stop working (format: YYYY-MM-DD)
        """
        
        return super()._get_field("effective_at", explicit_presence=False,
        )
    @effective_at.setter
    def effective_at(self, value: "builtins.str|None") -> None:
        return super()._set_field("effective_at",value,explicit_presence=False,
        )
    
    @builtins.property
    def description(self) -> "builtins.str":
        """
         A description to help users understand the reason for deprecation and suggest alternatives
        """
        
        return super()._get_field("description", explicit_presence=False,
        )
    @description.setter
    def description(self, value: "builtins.str|None") -> None:
        return super()._set_field("description",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "effective_at":"effective_at",
        "description":"description",
    }
    
api_service_name = annotations_pb2.api_service_name
service_deprecation_details = annotations_pb2.service_deprecation_details
method_deprecation_details = annotations_pb2.method_deprecation_details
region_routing = annotations_pb2.region_routing
resource_behavior = annotations_pb2.resource_behavior
message_deprecation_details = annotations_pb2.message_deprecation_details
field_behavior = annotations_pb2.field_behavior
sensitive = annotations_pb2.sensitive
credentials = annotations_pb2.credentials
field_deprecation_details = annotations_pb2.field_deprecation_details
oneof_behavior = annotations_pb2.oneof_behavior
enum_value_deprecation_details = annotations_pb2.enum_value_deprecation_details
__all__ = [
    #@ local import names here @#
    "ResourceBehavior",
    "FieldBehavior",
    "api_service_name",
    "service_deprecation_details",
    "method_deprecation_details",
    "region_routing",
    "resource_behavior",
    "message_deprecation_details",
    "field_behavior",
    "sensitive",
    "credentials",
    "field_deprecation_details",
    "oneof_behavior",
    "enum_value_deprecation_details",
    "RegionRouting",
    "DeprecationDetails",
]
