# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/msp/v1alpha1/resource/template_service.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as nebius_dot_msp_dot_v1alpha1_dot_resource_dot_template__pb2
from nebius.api.nebius import annotations_pb2 as nebius_dot_annotations__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n3nebius/msp/v1alpha1/resource/template_service.proto\x12\x1cnebius.msp.v1alpha1.resource\x1a+nebius/msp/v1alpha1/resource/template.proto\x1a\x18nebius/annotations.proto\"o\n\x14ListTemplatesRequest\x12\x1b\n\tpage_size\x18\x01 \x01(\x03R\x08pageSize\x12\x1d\n\npage_token\x18\x02 \x01(\tR\tpageToken\x12\x1b\n\tparent_id\x18\x03 \x01(\tR\x08parentId\"}\n\x15ListTemplatesResponse\x12<\n\x05items\x18\x01 \x03(\x0b\x32&.nebius.msp.v1alpha1.resource.TemplateR\x05items\x12&\n\x0fnext_page_token\x18\x02 \x01(\tR\rnextPageToken2\x91\x01\n\x0fTemplateService\x12o\n\x04List\x12\x32.nebius.msp.v1alpha1.resource.ListTemplatesRequest\x1a\x33.nebius.msp.v1alpha1.resource.ListTemplatesResponse\x1a\r\xbaJ\nmsp-commonBy\n#ai.nebius.pub.msp.v1alpha1.resourceB\x14TemplateServiceProtoP\x01Z:github.com/nebius/gosdk/proto/nebius/msp/v1alpha1/resourceb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.msp.v1alpha1.resource.template_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n#ai.nebius.pub.msp.v1alpha1.resourceB\024TemplateServiceProtoP\001Z:github.com/nebius/gosdk/proto/nebius/msp/v1alpha1/resource'
  _TEMPLATESERVICE._options = None
  _TEMPLATESERVICE._serialized_options = b'\272J\nmsp-common'
  _globals['_LISTTEMPLATESREQUEST']._serialized_start=156
  _globals['_LISTTEMPLATESREQUEST']._serialized_end=267
  _globals['_LISTTEMPLATESRESPONSE']._serialized_start=269
  _globals['_LISTTEMPLATESRESPONSE']._serialized_end=394
  _globals['_TEMPLATESERVICE']._serialized_start=397
  _globals['_TEMPLATESERVICE']._serialized_end=542
# @@protoc_insertion_point(module_scope)
