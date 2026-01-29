from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class StorageClass(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    STORAGE_CLASS_UNSPECIFIED: _ClassVar[StorageClass]
    STANDARD: _ClassVar[StorageClass]
    ENHANCED_THROUGHPUT: _ClassVar[StorageClass]
    INTELLIGENT_TIERING: _ClassVar[StorageClass]

class VersioningPolicy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    VERSIONING_POLICY_UNSPECIFIED: _ClassVar[VersioningPolicy]
    DISABLED: _ClassVar[VersioningPolicy]
    ENABLED: _ClassVar[VersioningPolicy]
    SUSPENDED: _ClassVar[VersioningPolicy]
STORAGE_CLASS_UNSPECIFIED: StorageClass
STANDARD: StorageClass
ENHANCED_THROUGHPUT: StorageClass
INTELLIGENT_TIERING: StorageClass
VERSIONING_POLICY_UNSPECIFIED: VersioningPolicy
DISABLED: VersioningPolicy
ENABLED: VersioningPolicy
SUSPENDED: VersioningPolicy
