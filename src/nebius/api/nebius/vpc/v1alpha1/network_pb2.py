# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/vpc/v1alpha1/network.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.buf.validate import validate_pb2 as buf_dot_validate_dot_validate__pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as nebius_dot_common_dot_v1_dot_metadata__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n!nebius/vpc/v1alpha1/network.proto\x12\x13nebius.vpc.v1alpha1\x1a\x1b\x62uf/validate/validate.proto\x1a\x1fnebius/common/v1/metadata.proto\"\xbb\x01\n\x07Network\x12>\n\x08metadata\x18\x01 \x01(\x0b\x32\".nebius.common.v1.ResourceMetadataR\x08metadata\x12\x34\n\x04spec\x18\x02 \x01(\x0b\x32 .nebius.vpc.v1alpha1.NetworkSpecR\x04spec\x12:\n\x06status\x18\x03 \x01(\x0b\x32\".nebius.vpc.v1alpha1.NetworkStatusR\x06status\"E\n\x0bNetworkSpec\x12\x36\n\x05pools\x18\x01 \x03(\x0b\x32 .nebius.vpc.v1alpha1.NetworkPoolR\x05pools\".\n\x0bNetworkPool\x12\x1f\n\x07pool_id\x18\x01 \x01(\tB\x06\xbaH\x03\xc8\x01\x01R\x06poolId\"\xb1\x01\n\rNetworkStatus\x12>\n\x05state\x18\x01 \x01(\x0e\x32(.nebius.vpc.v1alpha1.NetworkStatus.StateR\x05state\x12\x19\n\x08scope_id\x18\x02 \x01(\tR\x07scopeId\"E\n\x05State\x12\x15\n\x11STATE_UNSPECIFIED\x10\x00\x12\x0c\n\x08\x43REATING\x10\x01\x12\t\n\x05READY\x10\x02\x12\x0c\n\x08\x44\x45LETING\x10\x03\x42_\n\x1a\x61i.nebius.pub.vpc.v1alpha1B\x0cNetworkProtoP\x01Z1github.com/nebius/gosdk/proto/nebius/vpc/v1alpha1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.vpc.v1alpha1.network_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\032ai.nebius.pub.vpc.v1alpha1B\014NetworkProtoP\001Z1github.com/nebius/gosdk/proto/nebius/vpc/v1alpha1'
  _NETWORKPOOL.fields_by_name['pool_id']._options = None
  _NETWORKPOOL.fields_by_name['pool_id']._serialized_options = b'\272H\003\310\001\001'
  _globals['_NETWORK']._serialized_start=121
  _globals['_NETWORK']._serialized_end=308
  _globals['_NETWORKSPEC']._serialized_start=310
  _globals['_NETWORKSPEC']._serialized_end=379
  _globals['_NETWORKPOOL']._serialized_start=381
  _globals['_NETWORKPOOL']._serialized_end=427
  _globals['_NETWORKSTATUS']._serialized_start=430
  _globals['_NETWORKSTATUS']._serialized_end=607
  _globals['_NETWORKSTATUS_STATE']._serialized_start=538
  _globals['_NETWORKSTATUS_STATE']._serialized_end=607
# @@protoc_insertion_point(module_scope)
