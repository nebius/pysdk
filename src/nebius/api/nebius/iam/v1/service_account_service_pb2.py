# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/iam/v1/service_account_service.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.buf.validate import validate_pb2 as buf_dot_validate_dot_validate__pb2
from nebius.api.nebius import annotations_pb2 as nebius_dot_annotations__pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as nebius_dot_common_dot_v1_dot_metadata__pb2
from nebius.api.nebius.common.v1 import operation_pb2 as nebius_dot_common_dot_v1_dot_operation__pb2
from nebius.api.nebius.iam.v1 import service_account_pb2 as nebius_dot_iam_dot_v1_dot_service__account__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n+nebius/iam/v1/service_account_service.proto\x12\rnebius.iam.v1\x1a\x1b\x62uf/validate/validate.proto\x1a\x18nebius/annotations.proto\x1a\x1fnebius/common/v1/metadata.proto\x1a nebius/common/v1/operation.proto\x1a#nebius/iam/v1/service_account.proto\"\x94\x01\n\x1b\x43reateServiceAccountRequest\x12>\n\x08metadata\x18\x01 \x01(\x0b\x32\".nebius.common.v1.ResourceMetadataR\x08metadata\x12\x35\n\x04spec\x18\x02 \x01(\x0b\x32!.nebius.iam.v1.ServiceAccountSpecR\x04spec\"*\n\x18GetServiceAccountRequest\x12\x0e\n\x02id\x18\x01 \x01(\tR\x02id\"a\n\x1eGetServiceAccountByNameRequest\x12#\n\tparent_id\x18\x01 \x01(\tB\x06\xbaH\x03\xc8\x01\x01R\x08parentId\x12\x1a\n\x04name\x18\x02 \x01(\tB\x06\xbaH\x03\xc8\x01\x01R\x04name\"\x9f\x01\n\x19ListServiceAccountRequest\x12\x1b\n\tparent_id\x18\x01 \x01(\tR\x08parentId\x12 \n\tpage_size\x18\x02 \x01(\x03H\x00R\x08pageSize\x88\x01\x01\x12\x1d\n\npage_token\x18\x03 \x01(\tR\tpageToken\x12\x16\n\x06\x66ilter\x18\x04 \x01(\tR\x06\x66ilterB\x0c\n\n_page_size\"\x94\x01\n\x1bUpdateServiceAccountRequest\x12>\n\x08metadata\x18\x01 \x01(\x0b\x32\".nebius.common.v1.ResourceMetadataR\x08metadata\x12\x35\n\x04spec\x18\x02 \x01(\x0b\x32!.nebius.iam.v1.ServiceAccountSpecR\x04spec\"-\n\x1b\x44\x65leteServiceAccountRequest\x12\x0e\n\x02id\x18\x01 \x01(\tR\x02id\"y\n\x1aListServiceAccountResponse\x12\x33\n\x05items\x18\x01 \x03(\x0b\x32\x1d.nebius.iam.v1.ServiceAccountR\x05items\x12&\n\x0fnext_page_token\x18\x02 \x01(\tR\rnextPageToken2\xa3\x04\n\x15ServiceAccountService\x12Q\n\x06\x43reate\x12*.nebius.iam.v1.CreateServiceAccountRequest\x1a\x1b.nebius.common.v1.Operation\x12M\n\x03Get\x12\'.nebius.iam.v1.GetServiceAccountRequest\x1a\x1d.nebius.iam.v1.ServiceAccount\x12Y\n\tGetByName\x12-.nebius.iam.v1.GetServiceAccountByNameRequest\x1a\x1d.nebius.iam.v1.ServiceAccount\x12[\n\x04List\x12(.nebius.iam.v1.ListServiceAccountRequest\x1a).nebius.iam.v1.ListServiceAccountResponse\x12Q\n\x06Update\x12*.nebius.iam.v1.UpdateServiceAccountRequest\x1a\x1b.nebius.common.v1.Operation\x12Q\n\x06\x44\x65lete\x12*.nebius.iam.v1.DeleteServiceAccountRequest\x1a\x1b.nebius.common.v1.Operation\x1a\n\xbaJ\x07\x63pl.iamBa\n\x14\x61i.nebius.pub.iam.v1B\x1aServiceAccountServiceProtoP\x01Z+github.com/nebius/gosdk/proto/nebius/iam/v1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.iam.v1.service_account_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\024ai.nebius.pub.iam.v1B\032ServiceAccountServiceProtoP\001Z+github.com/nebius/gosdk/proto/nebius/iam/v1'
  _GETSERVICEACCOUNTBYNAMEREQUEST.fields_by_name['parent_id']._options = None
  _GETSERVICEACCOUNTBYNAMEREQUEST.fields_by_name['parent_id']._serialized_options = b'\272H\003\310\001\001'
  _GETSERVICEACCOUNTBYNAMEREQUEST.fields_by_name['name']._options = None
  _GETSERVICEACCOUNTBYNAMEREQUEST.fields_by_name['name']._serialized_options = b'\272H\003\310\001\001'
  _SERVICEACCOUNTSERVICE._options = None
  _SERVICEACCOUNTSERVICE._serialized_options = b'\272J\007cpl.iam'
  _globals['_CREATESERVICEACCOUNTREQUEST']._serialized_start=222
  _globals['_CREATESERVICEACCOUNTREQUEST']._serialized_end=370
  _globals['_GETSERVICEACCOUNTREQUEST']._serialized_start=372
  _globals['_GETSERVICEACCOUNTREQUEST']._serialized_end=414
  _globals['_GETSERVICEACCOUNTBYNAMEREQUEST']._serialized_start=416
  _globals['_GETSERVICEACCOUNTBYNAMEREQUEST']._serialized_end=513
  _globals['_LISTSERVICEACCOUNTREQUEST']._serialized_start=516
  _globals['_LISTSERVICEACCOUNTREQUEST']._serialized_end=675
  _globals['_UPDATESERVICEACCOUNTREQUEST']._serialized_start=678
  _globals['_UPDATESERVICEACCOUNTREQUEST']._serialized_end=826
  _globals['_DELETESERVICEACCOUNTREQUEST']._serialized_start=828
  _globals['_DELETESERVICEACCOUNTREQUEST']._serialized_end=873
  _globals['_LISTSERVICEACCOUNTRESPONSE']._serialized_start=875
  _globals['_LISTSERVICEACCOUNTRESPONSE']._serialized_end=996
  _globals['_SERVICEACCOUNTSERVICE']._serialized_start=999
  _globals['_SERVICEACCOUNTSERVICE']._serialized_end=1546
# @@protoc_insertion_point(module_scope)
