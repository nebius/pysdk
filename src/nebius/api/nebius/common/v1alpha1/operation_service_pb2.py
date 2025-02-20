# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/common/v1alpha1/operation_service.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.buf.validate import validate_pb2 as buf_dot_validate_dot_validate__pb2
from nebius.api.nebius.common.v1alpha1 import operation_pb2 as nebius_dot_common_dot_v1alpha1_dot_operation__pb2
from nebius.api.nebius import annotations_pb2 as nebius_dot_annotations__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n.nebius/common/v1alpha1/operation_service.proto\x12\x16nebius.common.v1alpha1\x1a\x1b\x62uf/validate/validate.proto\x1a&nebius/common/v1alpha1/operation.proto\x1a\x18nebius/annotations.proto\"1\n\x13GetOperationRequest\x12\x16\n\x02id\x18\x01 \x01(\tB\x06\xbaH\x03\xc8\x01\x01R\x02id:\x02\x18\x01\"\x98\x01\n\x15ListOperationsRequest\x12\'\n\x0bresource_id\x18\x01 \x01(\tB\x06\xbaH\x03\xc8\x01\x01R\nresourceId\x12\x1b\n\tpage_size\x18\x02 \x01(\x03R\x08pageSize\x12\x1d\n\npage_token\x18\x03 \x01(\tR\tpageToken\x12\x16\n\x06\x66ilter\x18\x04 \x01(\tR\x06\x66ilter:\x02\x18\x01\"\x87\x01\n\x16ListOperationsResponse\x12\x41\n\noperations\x18\x01 \x03(\x0b\x32!.nebius.common.v1alpha1.OperationR\noperations\x12&\n\x0fnext_page_token\x18\x02 \x01(\tR\rnextPageToken:\x02\x18\x01\"\x9c\x01\n\x1dListOperationsByParentRequest\x12#\n\tparent_id\x18\x01 \x01(\tB\x06\xbaH\x03\xc8\x01\x01R\x08parentId\x12\x1b\n\tpage_size\x18\x02 \x01(\x03R\x08pageSize\x12\x1d\n\npage_token\x18\x03 \x01(\tR\tpageToken\x12\x16\n\x06\x66ilter\x18\x04 \x01(\tR\x06\x66ilter:\x02\x18\x01\x32\xe8\x01\n\x10OperationService\x12U\n\x03Get\x12+.nebius.common.v1alpha1.GetOperationRequest\x1a!.nebius.common.v1alpha1.Operation\x12x\n\x04List\x12-.nebius.common.v1alpha1.ListOperationsRequest\x1a..nebius.common.v1alpha1.ListOperationsResponse\"\x11\x9a\xb5\x18\r\n\x0bresource_id\x1a\x03\x88\x02\x01\x42q\n\x1d\x61i.nebius.pub.common.v1alpha1B\x15OperationServiceProtoP\x01Z4github.com/nebius/gosdk/proto/nebius/common/v1alpha1\xb8\x01\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.common.v1alpha1.operation_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\035ai.nebius.pub.common.v1alpha1B\025OperationServiceProtoP\001Z4github.com/nebius/gosdk/proto/nebius/common/v1alpha1\270\001\001'
  _GETOPERATIONREQUEST.fields_by_name['id']._options = None
  _GETOPERATIONREQUEST.fields_by_name['id']._serialized_options = b'\272H\003\310\001\001'
  _GETOPERATIONREQUEST._options = None
  _GETOPERATIONREQUEST._serialized_options = b'\030\001'
  _LISTOPERATIONSREQUEST.fields_by_name['resource_id']._options = None
  _LISTOPERATIONSREQUEST.fields_by_name['resource_id']._serialized_options = b'\272H\003\310\001\001'
  _LISTOPERATIONSREQUEST._options = None
  _LISTOPERATIONSREQUEST._serialized_options = b'\030\001'
  _LISTOPERATIONSRESPONSE._options = None
  _LISTOPERATIONSRESPONSE._serialized_options = b'\030\001'
  _LISTOPERATIONSBYPARENTREQUEST.fields_by_name['parent_id']._options = None
  _LISTOPERATIONSBYPARENTREQUEST.fields_by_name['parent_id']._serialized_options = b'\272H\003\310\001\001'
  _LISTOPERATIONSBYPARENTREQUEST._options = None
  _LISTOPERATIONSBYPARENTREQUEST._serialized_options = b'\030\001'
  _OPERATIONSERVICE._options = None
  _OPERATIONSERVICE._serialized_options = b'\210\002\001'
  _OPERATIONSERVICE.methods_by_name['List']._options = None
  _OPERATIONSERVICE.methods_by_name['List']._serialized_options = b'\232\265\030\r\n\013resource_id'
  _globals['_GETOPERATIONREQUEST']._serialized_start=169
  _globals['_GETOPERATIONREQUEST']._serialized_end=218
  _globals['_LISTOPERATIONSREQUEST']._serialized_start=221
  _globals['_LISTOPERATIONSREQUEST']._serialized_end=373
  _globals['_LISTOPERATIONSRESPONSE']._serialized_start=376
  _globals['_LISTOPERATIONSRESPONSE']._serialized_end=511
  _globals['_LISTOPERATIONSBYPARENTREQUEST']._serialized_start=514
  _globals['_LISTOPERATIONSBYPARENTREQUEST']._serialized_end=670
  _globals['_OPERATIONSERVICE']._serialized_start=673
  _globals['_OPERATIONSERVICE']._serialized_end=905
# @@protoc_insertion_point(module_scope)
