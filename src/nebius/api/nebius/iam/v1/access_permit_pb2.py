# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/iam/v1/access_permit.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.nebius.common.v1 import metadata_pb2 as nebius_dot_common_dot_v1_dot_metadata__pb2
from nebius.api.nebius import annotations_pb2 as nebius_dot_annotations__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n!nebius/iam/v1/access_permit.proto\x12\rnebius.iam.v1\x1a\x1fnebius/common/v1/metadata.proto\x1a\x18nebius/annotations.proto\"\xca\x01\n\x0c\x41\x63\x63\x65ssPermit\x12>\n\x08metadata\x18\x01 \x01(\x0b\x32\".nebius.common.v1.ResourceMetadataR\x08metadata\x12\x33\n\x04spec\x18\x02 \x01(\x0b\x32\x1f.nebius.iam.v1.AccessPermitSpecR\x04spec\x12?\n\x06status\x18\x03 \x01(\x0b\x32!.nebius.iam.v1.AccessPermitStatusB\x04\xbaJ\x01\x05R\x06status:\x04\xbaJ\x01\x02\"S\n\x10\x41\x63\x63\x65ssPermitSpec\x12%\n\x0bresource_id\x18\x01 \x01(\tB\x04\xbaJ\x01\x02R\nresourceId\x12\x18\n\x04role\x18\x02 \x01(\tB\x04\xbaJ\x01\x02R\x04role\"\x14\n\x12\x41\x63\x63\x65ssPermitStatusBX\n\x14\x61i.nebius.pub.iam.v1B\x11\x41\x63\x63\x65ssPermitProtoP\x01Z+github.com/nebius/gosdk/proto/nebius/iam/v1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.iam.v1.access_permit_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\024ai.nebius.pub.iam.v1B\021AccessPermitProtoP\001Z+github.com/nebius/gosdk/proto/nebius/iam/v1'
  _ACCESSPERMIT.fields_by_name['status']._options = None
  _ACCESSPERMIT.fields_by_name['status']._serialized_options = b'\272J\001\005'
  _ACCESSPERMIT._options = None
  _ACCESSPERMIT._serialized_options = b'\272J\001\002'
  _ACCESSPERMITSPEC.fields_by_name['resource_id']._options = None
  _ACCESSPERMITSPEC.fields_by_name['resource_id']._serialized_options = b'\272J\001\002'
  _ACCESSPERMITSPEC.fields_by_name['role']._options = None
  _ACCESSPERMITSPEC.fields_by_name['role']._serialized_options = b'\272J\001\002'
  _globals['_ACCESSPERMIT']._serialized_start=112
  _globals['_ACCESSPERMIT']._serialized_end=314
  _globals['_ACCESSPERMITSPEC']._serialized_start=316
  _globals['_ACCESSPERMITSPEC']._serialized_end=399
  _globals['_ACCESSPERMITSTATUS']._serialized_start=401
  _globals['_ACCESSPERMITSTATUS']._serialized_end=421
# @@protoc_insertion_point(module_scope)
