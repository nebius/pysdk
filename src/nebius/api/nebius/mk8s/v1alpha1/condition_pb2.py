# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/mk8s/v1alpha1/condition.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n$nebius/mk8s/v1alpha1/condition.proto\x12\x14nebius.mk8s.v1alpha1\x1a\x1fgoogle/protobuf/timestamp.proto\"\xb2\x04\n\tCondition\x12\x12\n\x04type\x18\x01 \x01(\tR\x04type\x12>\n\x06status\x18\x02 \x01(\x0e\x32&.nebius.mk8s.v1alpha1.Condition.StatusR\x06status\x12H\n\x12last_transition_at\x18\x03 \x01(\x0b\x32\x1a.google.protobuf.TimestampR\x10lastTransitionAt\x12\x16\n\x06reason\x18\x04 \x01(\tR\x06reason\x12\x44\n\x08severity\x18\x05 \x01(\x0e\x32(.nebius.mk8s.v1alpha1.Condition.SeverityR\x08severity\x12 \n\x0b\x64\x65scription\x18\x06 \x01(\tR\x0b\x64\x65scription\x12\x63\n\x15last_transition_error\x18\x07 \x01(\x0b\x32/.nebius.mk8s.v1alpha1.Condition.TransitionErrorR\x13lastTransitionError\x1aK\n\x0fTransitionError\x12\x16\n\x06reason\x18\x01 \x01(\tR\x06reason\x12 \n\x0b\x64\x65scription\x18\x02 \x01(\tR\x0b\x64\x65scription\")\n\x08Severity\x12\x08\n\x04NONE\x10\x00\x12\x08\n\x04INFO\x10\x01\x12\t\n\x05\x45RROR\x10\x02\"*\n\x06Status\x12\x0b\n\x07UNKNOWN\x10\x00\x12\x08\n\x04TRUE\x10\x01\x12\t\n\x05\x46\x41LSE\x10\x02\x42\x63\n\x1b\x61i.nebius.pub.mk8s.v1alpha1B\x0e\x43onditionProtoP\x01Z2github.com/nebius/gosdk/proto/nebius/mk8s/v1alpha1b\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.mk8s.v1alpha1.condition_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\033ai.nebius.pub.mk8s.v1alpha1B\016ConditionProtoP\001Z2github.com/nebius/gosdk/proto/nebius/mk8s/v1alpha1'
  _globals['_CONDITION']._serialized_start=96
  _globals['_CONDITION']._serialized_end=658
  _globals['_CONDITION_TRANSITIONERROR']._serialized_start=496
  _globals['_CONDITION_TRANSITIONERROR']._serialized_end=571
  _globals['_CONDITION_SEVERITY']._serialized_start=573
  _globals['_CONDITION_SEVERITY']._serialized_end=614
  _globals['_CONDITION_STATUS']._serialized_start=616
  _globals['_CONDITION_STATUS']._serialized_end=658
# @@protoc_insertion_point(module_scope)
