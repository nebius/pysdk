from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius.common.v1alpha1 import operation_pb2 as _operation_pb2
from nebius.api.nebius.msp.postgresql.v1alpha1 import backup_pb2 as _backup_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetBackupRequest(_message.Message):
    __slots__ = ["cluster_id", "backup_id"]
    CLUSTER_ID_FIELD_NUMBER: _ClassVar[int]
    BACKUP_ID_FIELD_NUMBER: _ClassVar[int]
    cluster_id: str
    backup_id: str
    def __init__(self, cluster_id: _Optional[str] = ..., backup_id: _Optional[str] = ...) -> None: ...

class ListBackupsRequest(_message.Message):
    __slots__ = ["parent_id"]
    PARENT_ID_FIELD_NUMBER: _ClassVar[int]
    parent_id: str
    def __init__(self, parent_id: _Optional[str] = ...) -> None: ...

class ListBackupsByClusterRequest(_message.Message):
    __slots__ = ["cluster_id"]
    CLUSTER_ID_FIELD_NUMBER: _ClassVar[int]
    cluster_id: str
    def __init__(self, cluster_id: _Optional[str] = ...) -> None: ...

class ListBackupsResponse(_message.Message):
    __slots__ = ["backups"]
    BACKUPS_FIELD_NUMBER: _ClassVar[int]
    backups: _containers.RepeatedCompositeFieldContainer[_backup_pb2.Backup]
    def __init__(self, backups: _Optional[_Iterable[_Union[_backup_pb2.Backup, _Mapping]]] = ...) -> None: ...

class CreateBackupRequest(_message.Message):
    __slots__ = ["cluster_id"]
    CLUSTER_ID_FIELD_NUMBER: _ClassVar[int]
    cluster_id: str
    def __init__(self, cluster_id: _Optional[str] = ...) -> None: ...

class DeleteBackupRequest(_message.Message):
    __slots__ = ["cluster_id", "backup_id"]
    CLUSTER_ID_FIELD_NUMBER: _ClassVar[int]
    BACKUP_ID_FIELD_NUMBER: _ClassVar[int]
    cluster_id: str
    backup_id: str
    def __init__(self, cluster_id: _Optional[str] = ..., backup_id: _Optional[str] = ...) -> None: ...
