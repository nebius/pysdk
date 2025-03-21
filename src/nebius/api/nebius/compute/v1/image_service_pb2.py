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


from nebius.api.nebius.common.v1 import metadata_pb2 as nebius_dot_common_dot_v1_dot_metadata__pb2
from nebius.api.nebius.common.v1 import operation_service_pb2 as nebius_dot_common_dot_v1_dot_operation__service__pb2
from nebius.api.nebius.compute.v1 import image_pb2 as nebius_dot_compute_dot_v1_dot_image__pb2
from nebius.api.nebius.compute.v1 import operation_service_pb2 as nebius_dot_compute_dot_v1_dot_operation__service__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n%nebius/compute/v1/image_service.proto\x12\x11nebius.compute.v1\x1a\x1fnebius/common/v1/metadata.proto\x1a(nebius/common/v1/operation_service.proto\x1a\x1dnebius/compute/v1/image.proto\x1a)nebius/compute/v1/operation_service.proto\"!\n\x0fGetImageRequest\x12\x0e\n\x02id\x18\x01 \x01(\tR\x02id\"_\n\x1dGetImageLatestByFamilyRequest\x12!\n\x0cimage_family\x18\x01 \x01(\tR\x0bimageFamily\x12\x1b\n\tparent_id\x18\x02 \x01(\tR\x08parentId\"\x84\x01\n\x11ListImagesRequest\x12\x1b\n\tparent_id\x18\x01 \x01(\tR\x08parentId\x12\x1b\n\tpage_size\x18\x02 \x01(\x03R\x08pageSize\x12\x1d\n\npage_token\x18\x03 \x01(\tR\tpageToken\x12\x16\n\x06\x66ilter\x18\x04 \x01(\tR\x06\x66ilter\"l\n\x12ListImagesResponse\x12.\n\x05items\x18\x01 \x03(\x0b\x32\x18.nebius.compute.v1.ImageR\x05items\x12&\n\x0fnext_page_token\x18\x02 \x01(\tR\rnextPageToken2\xca\x03\n\x0cImageService\x12\x43\n\x03Get\x12\".nebius.compute.v1.GetImageRequest\x1a\x18.nebius.compute.v1.Image\x12I\n\tGetByName\x12\".nebius.common.v1.GetByNameRequest\x1a\x18.nebius.compute.v1.Image\x12_\n\x11GetLatestByFamily\x12\x30.nebius.compute.v1.GetImageLatestByFamilyRequest\x1a\x18.nebius.compute.v1.Image\x12S\n\x04List\x12$.nebius.compute.v1.ListImagesRequest\x1a%.nebius.compute.v1.ListImagesResponse\x12t\n\x16ListOperationsByParent\x12\x30.nebius.compute.v1.ListOperationsByParentRequest\x1a(.nebius.common.v1.ListOperationsResponseB`\n\x18\x61i.nebius.pub.compute.v1B\x11ImageServiceProtoP\x01Z/github.com/nebius/gosdk/proto/nebius/compute/v1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.compute.v1.image_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\030ai.nebius.pub.compute.v1B\021ImageServiceProtoP\001Z/github.com/nebius/gosdk/proto/nebius/compute/v1'
  _globals['_GETIMAGEREQUEST']._serialized_start=209
  _globals['_GETIMAGEREQUEST']._serialized_end=242
  _globals['_GETIMAGELATESTBYFAMILYREQUEST']._serialized_start=244
  _globals['_GETIMAGELATESTBYFAMILYREQUEST']._serialized_end=339
  _globals['_LISTIMAGESREQUEST']._serialized_start=342
  _globals['_LISTIMAGESREQUEST']._serialized_end=474
  _globals['_LISTIMAGESRESPONSE']._serialized_start=476
  _globals['_LISTIMAGESRESPONSE']._serialized_end=584
  _globals['_IMAGESERVICE']._serialized_start=587
  _globals['_IMAGESERVICE']._serialized_end=1045
# @@protoc_insertion_point(module_scope)
