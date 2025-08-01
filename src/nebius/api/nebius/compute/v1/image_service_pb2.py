# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/compute/v1/image_service.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.nebius import annotations_pb2 as nebius_dot_annotations__pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as nebius_dot_common_dot_v1_dot_metadata__pb2
from nebius.api.nebius.common.v1 import operation_service_pb2 as nebius_dot_common_dot_v1_dot_operation__service__pb2
from nebius.api.nebius.compute.v1 import image_pb2 as nebius_dot_compute_dot_v1_dot_image__pb2
from nebius.api.nebius.compute.v1 import operation_service_pb2 as nebius_dot_compute_dot_v1_dot_operation__service__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n%nebius/compute/v1/image_service.proto\x12\x11nebius.compute.v1\x1a\x18nebius/annotations.proto\x1a\x1fnebius/common/v1/metadata.proto\x1a(nebius/common/v1/operation_service.proto\x1a\x1dnebius/compute/v1/image.proto\x1a)nebius/compute/v1/operation_service.proto\"!\n\x0fGetImageRequest\x12\x0e\n\x02id\x18\x01 \x01(\tR\x02id\"_\n\x1dGetImageLatestByFamilyRequest\x12!\n\x0cimage_family\x18\x01 \x01(\tR\x0bimageFamily\x12\x1b\n\tparent_id\x18\x02 \x01(\tR\x08parentId\"\xd6\x01\n\x11ListImagesRequest\x12\x1b\n\tparent_id\x18\x01 \x01(\tR\x08parentId\x12\x1b\n\tpage_size\x18\x02 \x01(\x03R\x08pageSize\x12\x1d\n\npage_token\x18\x03 \x01(\tR\tpageToken\x12h\n\x06\x66ilter\x18\x04 \x01(\tBP\x18\x01\xd2JK\n\n2025-06-16\x12=it is not implemented, filtering could be done on client sideR\x06\x66ilter\"l\n\x12ListImagesResponse\x12.\n\x05items\x18\x01 \x03(\x0b\x32\x18.nebius.compute.v1.ImageR\x05items\x12&\n\x0fnext_page_token\x18\x02 \x01(\tR\rnextPageToken2\xd6\x03\n\x0cImageService\x12\x43\n\x03Get\x12\".nebius.compute.v1.GetImageRequest\x1a\x18.nebius.compute.v1.Image\x12I\n\tGetByName\x12\".nebius.common.v1.GetByNameRequest\x1a\x18.nebius.compute.v1.Image\x12_\n\x11GetLatestByFamily\x12\x30.nebius.compute.v1.GetImageLatestByFamilyRequest\x1a\x18.nebius.compute.v1.Image\x12S\n\x04List\x12$.nebius.compute.v1.ListImagesRequest\x1a%.nebius.compute.v1.ListImagesResponse\x12t\n\x16ListOperationsByParent\x12\x30.nebius.compute.v1.ListOperationsByParentRequest\x1a(.nebius.common.v1.ListOperationsResponse\x1a\n\xbaJ\x07\x63omputeB`\n\x18\x61i.nebius.pub.compute.v1B\x11ImageServiceProtoP\x01Z/github.com/nebius/gosdk/proto/nebius/compute/v1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.compute.v1.image_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\030ai.nebius.pub.compute.v1B\021ImageServiceProtoP\001Z/github.com/nebius/gosdk/proto/nebius/compute/v1'
  _LISTIMAGESREQUEST.fields_by_name['filter']._options = None
  _LISTIMAGESREQUEST.fields_by_name['filter']._serialized_options = b'\030\001\322JK\n\n2025-06-16\022=it is not implemented, filtering could be done on client side'
  _IMAGESERVICE._options = None
  _IMAGESERVICE._serialized_options = b'\272J\007compute'
  _globals['_GETIMAGEREQUEST']._serialized_start=235
  _globals['_GETIMAGEREQUEST']._serialized_end=268
  _globals['_GETIMAGELATESTBYFAMILYREQUEST']._serialized_start=270
  _globals['_GETIMAGELATESTBYFAMILYREQUEST']._serialized_end=365
  _globals['_LISTIMAGESREQUEST']._serialized_start=368
  _globals['_LISTIMAGESREQUEST']._serialized_end=582
  _globals['_LISTIMAGESRESPONSE']._serialized_start=584
  _globals['_LISTIMAGESRESPONSE']._serialized_end=692
  _globals['_IMAGESERVICE']._serialized_start=695
  _globals['_IMAGESERVICE']._serialized_end=1165
# @@protoc_insertion_point(module_scope)
