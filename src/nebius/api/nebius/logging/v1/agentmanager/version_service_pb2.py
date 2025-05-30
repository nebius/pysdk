# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: nebius/logging/v1/agentmanager/version_service.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import duration_pb2 as google_dot_protobuf_dot_duration__pb2
from nebius.api.nebius import annotations_pb2 as nebius_dot_annotations__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n4nebius/logging/v1/agentmanager/version_service.proto\x12\x1enebius.logging.agentmanager.v1\x1a\x1egoogle/protobuf/duration.proto\x1a\x18nebius/annotations.proto\"\xf6\x07\n\x11GetVersionRequest\x12=\n\x04type\x18\x01 \x01(\x0e\x32).nebius.logging.agentmanager.v1.AgentTypeR\x04type\x12#\n\ragent_version\x18\x02 \x01(\tR\x0c\x61gentVersion\x12\'\n\x0fupdater_version\x18\x03 \x01(\tR\x0eupdaterVersion\x12\x1b\n\tparent_id\x18\x04 \x01(\tR\x08parentId\x12\x1f\n\x0binstance_id\x18\x05 \x01(\tR\ninstanceId\x12?\n\x07os_info\x18\x06 \x01(\x0b\x32&.nebius.logging.agentmanager.v1.OSInfoR\x06osInfo\x12K\n\x0b\x61gent_state\x18\x07 \x01(\x0e\x32*.nebius.logging.agentmanager.v1.AgentStateR\nagentState\x12<\n\x0c\x61gent_uptime\x18\x08 \x01(\x0b\x32\x19.google.protobuf.DurationR\x0b\x61gentUptime\x12>\n\rsystem_uptime\x18\t \x01(\x0b\x32\x19.google.protobuf.DurationR\x0csystemUptime\x12@\n\x0eupdater_uptime\x18\n \x01(\x0b\x32\x19.google.protobuf.DurationR\rupdaterUptime\x12\x30\n\x14\x61gent_state_messages\x18\x0b \x03(\tR\x12\x61gentStateMessages\x12*\n\x11last_update_error\x18\x0c \x01(\tR\x0flastUpdateError\x12&\n\x0fmk8s_cluster_id\x18\r \x01(\tR\rmk8sClusterId\x12T\n\x0emodules_health\x18\x0e \x01(\x0b\x32-.nebius.logging.agentmanager.v1.ModulesHealthR\rmodulesHealth\x12*\n\x11\x63loud_init_status\x18\x0f \x01(\tR\x0f\x63loudInitStatus\x12\x39\n\x19instance_id_used_fallback\x18\x10 \x01(\x08R\x16instanceIdUsedFallback\x12&\n\x0flast_agent_logs\x18\x11 \x01(\tR\rlastAgentLogs\x12\x1b\n\tgpu_model\x18\x12 \x01(\tR\x08gpuModel\x12\x1d\n\ngpu_number\x18\x13 \x01(\x05R\tgpuNumber\x12!\n\x0c\x64\x63gm_version\x18\x14 \x01(\tR\x0b\x64\x63gmVersion\"\xd0\x02\n\rModulesHealth\x12\x46\n\x07process\x18\x01 \x01(\x0b\x32,.nebius.logging.agentmanager.v1.ModuleHealthR\x07process\x12O\n\x0cgpu_pipeline\x18\x02 \x01(\x0b\x32,.nebius.logging.agentmanager.v1.ModuleHealthR\x0bgpuPipeline\x12O\n\x0c\x63pu_pipeline\x18\x03 \x01(\x0b\x32,.nebius.logging.agentmanager.v1.ModuleHealthR\x0b\x63puPipeline\x12U\n\x0f\x63ilium_pipeline\x18\x04 \x01(\x0b\x32,.nebius.logging.agentmanager.v1.ModuleHealthR\x0e\x63iliumPipeline\"\xb7\x01\n\x0cModuleHealth\x12@\n\x05state\x18\x01 \x01(\x0e\x32*.nebius.logging.agentmanager.v1.AgentStateR\x05state\x12\x1a\n\x08messages\x18\x02 \x03(\tR\x08messages\x12I\n\nparameters\x18\x03 \x03(\x0b\x32).nebius.logging.agentmanager.v1.ParameterR\nparameters\"5\n\tParameter\x12\x12\n\x04name\x18\x01 \x01(\tR\x04name\x12\x14\n\x05value\x18\x02 \x01(\tR\x05value\"V\n\x06OSInfo\x12\x12\n\x04name\x18\x01 \x01(\tR\x04name\x12\x14\n\x05uname\x18\x02 \x01(\tR\x05uname\x12\"\n\x0c\x61rchitecture\x18\x03 \x01(\tR\x0c\x61rchitecture\"\xc4\x02\n\x12GetVersionResponse\x12>\n\x06\x61\x63tion\x18\x01 \x01(\x0e\x32&.nebius.logging.agentmanager.v1.ActionR\x06\x61\x63tion\x12\x43\n\x03nop\x18\x02 \x01(\x0b\x32/.nebius.logging.agentmanager.v1.NopActionParamsH\x00R\x03nop\x12L\n\x06update\x18\x03 \x01(\x0b\x32\x32.nebius.logging.agentmanager.v1.UpdateActionParamsH\x00R\x06update\x12O\n\x07restart\x18\x04 \x01(\x0b\x32\x33.nebius.logging.agentmanager.v1.RestartActionParamsH\x00R\x07restartB\n\n\x08response\"\x11\n\x0fNopActionParams\"I\n\x12UpdateActionParams\x12\x18\n\x07version\x18\x01 \x01(\tR\x07version\x12\x19\n\x08repo_url\x18\x02 \x01(\tR\x07repoUrl\"\x15\n\x13RestartActionParams*0\n\tAgentType\x12\x13\n\x0f\x41GENT_UNDEFINED\x10\x00\x12\x0e\n\nO11Y_AGENT\x10\x01*E\n\nAgentState\x12\x13\n\x0fSTATE_UNDEFINED\x10\x00\x12\x11\n\rSTATE_HEALTHY\x10\x01\x12\x0f\n\x0bSTATE_ERROR\x10\x02*@\n\x06\x41\x63tion\x12\x14\n\x10\x41\x43TION_UNDEFINED\x10\x00\x12\x07\n\x03NOP\x10\x01\x12\n\n\x06UPDATE\x10\x02\x12\x0b\n\x07RESTART\x10\x03\x32\xb9\x01\n\x0eVersionService\x12\x86\x01\n\nGetVersion\x12\x31.nebius.logging.agentmanager.v1.GetVersionRequest\x1a\x32.nebius.logging.agentmanager.v1.GetVersionResponse\"\x11\x9a\xb5\x18\r\n\x0binstance_id\x1a\x1e\xbaJ\x1bobservability-agent-managerB|\n%ai.nebius.pub.logging.v1.agentmanagerB\x13VersionServiceProtoP\x01Z<github.com/nebius/gosdk/proto/nebius/logging/v1/agentmanagerb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'nebius.logging.v1.agentmanager.version_service_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n%ai.nebius.pub.logging.v1.agentmanagerB\023VersionServiceProtoP\001Z<github.com/nebius/gosdk/proto/nebius/logging/v1/agentmanager'
  _VERSIONSERVICE._options = None
  _VERSIONSERVICE._serialized_options = b'\272J\033observability-agent-manager'
  _VERSIONSERVICE.methods_by_name['GetVersion']._options = None
  _VERSIONSERVICE.methods_by_name['GetVersion']._serialized_options = b'\232\265\030\r\n\013instance_id'
  _globals['_AGENTTYPE']._serialized_start=2275
  _globals['_AGENTTYPE']._serialized_end=2323
  _globals['_AGENTSTATE']._serialized_start=2325
  _globals['_AGENTSTATE']._serialized_end=2394
  _globals['_ACTION']._serialized_start=2396
  _globals['_ACTION']._serialized_end=2460
  _globals['_GETVERSIONREQUEST']._serialized_start=147
  _globals['_GETVERSIONREQUEST']._serialized_end=1161
  _globals['_MODULESHEALTH']._serialized_start=1164
  _globals['_MODULESHEALTH']._serialized_end=1500
  _globals['_MODULEHEALTH']._serialized_start=1503
  _globals['_MODULEHEALTH']._serialized_end=1686
  _globals['_PARAMETER']._serialized_start=1688
  _globals['_PARAMETER']._serialized_end=1741
  _globals['_OSINFO']._serialized_start=1743
  _globals['_OSINFO']._serialized_end=1829
  _globals['_GETVERSIONRESPONSE']._serialized_start=1832
  _globals['_GETVERSIONRESPONSE']._serialized_end=2156
  _globals['_NOPACTIONPARAMS']._serialized_start=2158
  _globals['_NOPACTIONPARAMS']._serialized_end=2175
  _globals['_UPDATEACTIONPARAMS']._serialized_start=2177
  _globals['_UPDATEACTIONPARAMS']._serialized_end=2250
  _globals['_RESTARTACTIONPARAMS']._serialized_start=2252
  _globals['_RESTARTACTIONPARAMS']._serialized_end=2273
  _globals['_VERSIONSERVICE']._serialized_start=2463
  _globals['_VERSIONSERVICE']._serialized_end=2648
# @@protoc_insertion_point(module_scope)
