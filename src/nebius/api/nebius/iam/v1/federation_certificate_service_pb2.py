# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/iam/v1/federation_certificate_service.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from nebius.api.nebius import annotations_pb2 as nebius_dot_annotations__pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as nebius_dot_common_dot_v1_dot_metadata__pb2
from nebius.api.nebius.common.v1 import operation_pb2 as nebius_dot_common_dot_v1_dot_operation__pb2
from nebius.api.nebius.iam.v1 import federation_certificate_pb2 as nebius_dot_iam_dot_v1_dot_federation__certificate__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n2nebius/iam/v1/federation_certificate_service.proto\x12\rnebius.iam.v1\x1a\x18nebius/annotations.proto\x1a\x1fnebius/common/v1/metadata.proto\x1a nebius/common/v1/operation.proto\x1a*nebius/iam/v1/federation_certificate.proto\"\xa2\x01\n\"CreateFederationCertificateRequest\x12>\n\x08metadata\x18\x01 \x01(\x0b\x32\".nebius.common.v1.ResourceMetadataR\x08metadata\x12<\n\x04spec\x18\x02 \x01(\x0b\x32(.nebius.iam.v1.FederationCertificateSpecR\x04spec\"1\n\x1fGetFederationCertificateRequest\x12\x0e\n\x02id\x18\x01 \x01(\tR\x02id\"\x8f\x01\n,ListFederationCertificateByFederationRequest\x12#\n\rfederation_id\x18\x01 \x01(\tR\x0c\x66\x65\x64\x65rationId\x12\x1b\n\tpage_size\x18\x02 \x01(\x03R\x08pageSize\x12\x1d\n\npage_token\x18\x03 \x01(\tR\tpageToken\"\xa2\x01\n\"UpdateFederationCertificateRequest\x12>\n\x08metadata\x18\x01 \x01(\x0b\x32\".nebius.common.v1.ResourceMetadataR\x08metadata\x12<\n\x04spec\x18\x02 \x01(\x0b\x32(.nebius.iam.v1.FederationCertificateSpecR\x04spec\"4\n\"DeleteFederationCertificateRequest\x12\x0e\n\x02id\x18\x01 \x01(\tR\x02id\"\x87\x01\n!ListFederationCertificateResponse\x12:\n\x05items\x18\x01 \x03(\x0b\x32$.nebius.iam.v1.FederationCertificateR\x05items\x12&\n\x0fnext_page_token\x18\x02 \x01(\tR\rnextPageToken2\x99\x04\n\x1c\x46\x65\x64\x65rationCertificateService\x12X\n\x06\x43reate\x12\x31.nebius.iam.v1.CreateFederationCertificateRequest\x1a\x1b.nebius.common.v1.Operation\x12[\n\x03Get\x12..nebius.iam.v1.GetFederationCertificateRequest\x1a$.nebius.iam.v1.FederationCertificate\x12\x81\x01\n\x10ListByFederation\x12;.nebius.iam.v1.ListFederationCertificateByFederationRequest\x1a\x30.nebius.iam.v1.ListFederationCertificateResponse\x12X\n\x06Update\x12\x31.nebius.iam.v1.UpdateFederationCertificateRequest\x1a\x1b.nebius.common.v1.Operation\x12X\n\x06\x44\x65lete\x12\x31.nebius.iam.v1.DeleteFederationCertificateRequest\x1a\x1b.nebius.common.v1.Operation\x1a\n\xbaJ\x07\x63pl.iamBh\n\x14\x61i.nebius.pub.iam.v1B!FederationCertificateServiceProtoP\x01Z+github.com/nebius/gosdk/proto/nebius/iam/v1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.iam.v1.federation_certificate_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\024ai.nebius.pub.iam.v1B!FederationCertificateServiceProtoP\001Z+github.com/nebius/gosdk/proto/nebius/iam/v1'
  _FEDERATIONCERTIFICATESERVICE._options = None
  _FEDERATIONCERTIFICATESERVICE._serialized_options = b'\272J\007cpl.iam'
  _globals['_CREATEFEDERATIONCERTIFICATEREQUEST']._serialized_start=207
  _globals['_CREATEFEDERATIONCERTIFICATEREQUEST']._serialized_end=369
  _globals['_GETFEDERATIONCERTIFICATEREQUEST']._serialized_start=371
  _globals['_GETFEDERATIONCERTIFICATEREQUEST']._serialized_end=420
  _globals['_LISTFEDERATIONCERTIFICATEBYFEDERATIONREQUEST']._serialized_start=423
  _globals['_LISTFEDERATIONCERTIFICATEBYFEDERATIONREQUEST']._serialized_end=566
  _globals['_UPDATEFEDERATIONCERTIFICATEREQUEST']._serialized_start=569
  _globals['_UPDATEFEDERATIONCERTIFICATEREQUEST']._serialized_end=731
  _globals['_DELETEFEDERATIONCERTIFICATEREQUEST']._serialized_start=733
  _globals['_DELETEFEDERATIONCERTIFICATEREQUEST']._serialized_end=785
  _globals['_LISTFEDERATIONCERTIFICATERESPONSE']._serialized_start=788
  _globals['_LISTFEDERATIONCERTIFICATERESPONSE']._serialized_end=923
  _globals['_FEDERATIONCERTIFICATESERVICE']._serialized_start=926
  _globals['_FEDERATIONCERTIFICATESERVICE']._serialized_end=1463
# @@protoc_insertion_point(module_scope)
