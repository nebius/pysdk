# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/msp/postgresql/v1alpha1/template.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.buf.validate import validate_pb2 as buf_dot_validate_dot_validate__pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as nebius_dot_msp_dot_v1alpha1_dot_resource_dot_template__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n-nebius/msp/postgresql/v1alpha1/template.proto\x12\x1enebius.msp.postgresql.v1alpha1\x1a\x1b\x62uf/validate/validate.proto\x1a+nebius/msp/v1alpha1/resource/template.proto\"\xeb\x01\n\x0cTemplateSpec\x12Q\n\tresources\x18\x01 \x01(\x0b\x32+.nebius.msp.v1alpha1.resource.ResourcesSpecB\x06\xbaH\x03\xc8\x01\x01R\tresources\x12\x44\n\x05hosts\x18\x02 \x01(\x0b\x32&.nebius.msp.v1alpha1.resource.HostSpecB\x06\xbaH\x03\xc8\x01\x01R\x05hosts\x12\x42\n\x04\x64isk\x18\x03 \x01(\x0b\x32&.nebius.msp.v1alpha1.resource.DiskSpecB\x06\xbaH\x03\xc8\x01\x01R\x04\x64iskBv\n%ai.nebius.pub.msp.postgresql.v1alpha1B\rTemplateProtoP\x01Z<github.com/nebius/gosdk/proto/nebius/msp/postgresql/v1alpha1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.msp.postgresql.v1alpha1.template_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n%ai.nebius.pub.msp.postgresql.v1alpha1B\rTemplateProtoP\001Z<github.com/nebius/gosdk/proto/nebius/msp/postgresql/v1alpha1'
  _TEMPLATESPEC.fields_by_name['resources']._options = None
  _TEMPLATESPEC.fields_by_name['resources']._serialized_options = b'\272H\003\310\001\001'
  _TEMPLATESPEC.fields_by_name['hosts']._options = None
  _TEMPLATESPEC.fields_by_name['hosts']._serialized_options = b'\272H\003\310\001\001'
  _TEMPLATESPEC.fields_by_name['disk']._options = None
  _TEMPLATESPEC.fields_by_name['disk']._serialized_options = b'\272H\003\310\001\001'
  _globals['_TEMPLATESPEC']._serialized_start=156
  _globals['_TEMPLATESPEC']._serialized_end=391
# @@protoc_insertion_point(module_scope)
