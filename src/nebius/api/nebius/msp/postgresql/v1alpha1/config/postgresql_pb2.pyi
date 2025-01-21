from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PostgresqlConfig16(_message.Message):
    __slots__ = ["autovacuum_work_mem", "statement_timeout", "idle_in_transaction_session_timeout", "autovacuum_vacuum_cost_delay", "autovacuum_vacuum_cost_limit", "autovacuum_naptime", "autovacuum_vacuum_scale_factor", "autovacuum_analyze_scale_factor", "default_transaction_read_only", "search_path", "max_connections", "shared_buffers"]
    AUTOVACUUM_WORK_MEM_FIELD_NUMBER: _ClassVar[int]
    STATEMENT_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    IDLE_IN_TRANSACTION_SESSION_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    AUTOVACUUM_VACUUM_COST_DELAY_FIELD_NUMBER: _ClassVar[int]
    AUTOVACUUM_VACUUM_COST_LIMIT_FIELD_NUMBER: _ClassVar[int]
    AUTOVACUUM_NAPTIME_FIELD_NUMBER: _ClassVar[int]
    AUTOVACUUM_VACUUM_SCALE_FACTOR_FIELD_NUMBER: _ClassVar[int]
    AUTOVACUUM_ANALYZE_SCALE_FACTOR_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_TRANSACTION_READ_ONLY_FIELD_NUMBER: _ClassVar[int]
    SEARCH_PATH_FIELD_NUMBER: _ClassVar[int]
    MAX_CONNECTIONS_FIELD_NUMBER: _ClassVar[int]
    SHARED_BUFFERS_FIELD_NUMBER: _ClassVar[int]
    autovacuum_work_mem: int
    statement_timeout: int
    idle_in_transaction_session_timeout: int
    autovacuum_vacuum_cost_delay: int
    autovacuum_vacuum_cost_limit: int
    autovacuum_naptime: int
    autovacuum_vacuum_scale_factor: float
    autovacuum_analyze_scale_factor: float
    default_transaction_read_only: bool
    search_path: str
    max_connections: int
    shared_buffers: int
    def __init__(self, autovacuum_work_mem: _Optional[int] = ..., statement_timeout: _Optional[int] = ..., idle_in_transaction_session_timeout: _Optional[int] = ..., autovacuum_vacuum_cost_delay: _Optional[int] = ..., autovacuum_vacuum_cost_limit: _Optional[int] = ..., autovacuum_naptime: _Optional[int] = ..., autovacuum_vacuum_scale_factor: _Optional[float] = ..., autovacuum_analyze_scale_factor: _Optional[float] = ..., default_transaction_read_only: bool = ..., search_path: _Optional[str] = ..., max_connections: _Optional[int] = ..., shared_buffers: _Optional[int] = ...) -> None: ...
