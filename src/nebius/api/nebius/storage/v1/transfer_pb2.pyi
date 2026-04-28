from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from google.protobuf import duration_pb2 as _duration_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Transfer(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: TransferSpec
    status: TransferStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[TransferSpec, _Mapping]] = ..., status: _Optional[_Union[TransferStatus, _Mapping]] = ...) -> None: ...

class TransferSpec(_message.Message):
    __slots__ = ["source", "destination", "limiters", "after_one_iteration", "after_n_empty_iterations", "infinite", "inter_iteration_interval", "overwrite_strategy", "touch_unmanaged"]
    class OverwriteStrategy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        OVERWRITE_STRATEGY_UNSPECIFIED: _ClassVar[TransferSpec.OverwriteStrategy]
        NEVER: _ClassVar[TransferSpec.OverwriteStrategy]
        IF_NEWER: _ClassVar[TransferSpec.OverwriteStrategy]
    OVERWRITE_STRATEGY_UNSPECIFIED: TransferSpec.OverwriteStrategy
    NEVER: TransferSpec.OverwriteStrategy
    IF_NEWER: TransferSpec.OverwriteStrategy
    class Limiters(_message.Message):
        __slots__ = ["bandwidth_bytes_per_second", "requests_per_second"]
        BANDWIDTH_BYTES_PER_SECOND_FIELD_NUMBER: _ClassVar[int]
        REQUESTS_PER_SECOND_FIELD_NUMBER: _ClassVar[int]
        bandwidth_bytes_per_second: int
        requests_per_second: int
        def __init__(self, bandwidth_bytes_per_second: _Optional[int] = ..., requests_per_second: _Optional[int] = ...) -> None: ...
    class StopConditionAfterOneIteration(_message.Message):
        __slots__ = []
        def __init__(self) -> None: ...
    class StopConditionAfterNEmptyIterations(_message.Message):
        __slots__ = ["empty_iterations_threshold"]
        EMPTY_ITERATIONS_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
        empty_iterations_threshold: int
        def __init__(self, empty_iterations_threshold: _Optional[int] = ...) -> None: ...
    class StopConditionInfinite(_message.Message):
        __slots__ = []
        def __init__(self) -> None: ...
    SOURCE_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_FIELD_NUMBER: _ClassVar[int]
    LIMITERS_FIELD_NUMBER: _ClassVar[int]
    AFTER_ONE_ITERATION_FIELD_NUMBER: _ClassVar[int]
    AFTER_N_EMPTY_ITERATIONS_FIELD_NUMBER: _ClassVar[int]
    INFINITE_FIELD_NUMBER: _ClassVar[int]
    INTER_ITERATION_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    OVERWRITE_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    TOUCH_UNMANAGED_FIELD_NUMBER: _ClassVar[int]
    source: TransferSource
    destination: TransferDestination
    limiters: TransferSpec.Limiters
    after_one_iteration: TransferSpec.StopConditionAfterOneIteration
    after_n_empty_iterations: TransferSpec.StopConditionAfterNEmptyIterations
    infinite: TransferSpec.StopConditionInfinite
    inter_iteration_interval: _duration_pb2.Duration
    overwrite_strategy: TransferSpec.OverwriteStrategy
    touch_unmanaged: bool
    def __init__(self, source: _Optional[_Union[TransferSource, _Mapping]] = ..., destination: _Optional[_Union[TransferDestination, _Mapping]] = ..., limiters: _Optional[_Union[TransferSpec.Limiters, _Mapping]] = ..., after_one_iteration: _Optional[_Union[TransferSpec.StopConditionAfterOneIteration, _Mapping]] = ..., after_n_empty_iterations: _Optional[_Union[TransferSpec.StopConditionAfterNEmptyIterations, _Mapping]] = ..., infinite: _Optional[_Union[TransferSpec.StopConditionInfinite, _Mapping]] = ..., inter_iteration_interval: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., overwrite_strategy: _Optional[_Union[TransferSpec.OverwriteStrategy, str]] = ..., touch_unmanaged: bool = ...) -> None: ...

class TransferSource(_message.Message):
    __slots__ = ["nebius", "s3_compatible", "azure_blob_storage", "prefix"]
    class NebiusProvider(_message.Message):
        __slots__ = ["region", "bucket_name", "anonymous", "access_key"]
        REGION_FIELD_NUMBER: _ClassVar[int]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        ANONYMOUS_FIELD_NUMBER: _ClassVar[int]
        ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
        region: str
        bucket_name: str
        anonymous: TransferCredentialsAnonymous
        access_key: TransferCredentialsAccessKey
        def __init__(self, region: _Optional[str] = ..., bucket_name: _Optional[str] = ..., anonymous: _Optional[_Union[TransferCredentialsAnonymous, _Mapping]] = ..., access_key: _Optional[_Union[TransferCredentialsAccessKey, _Mapping]] = ...) -> None: ...
    class S3CompatibleProvider(_message.Message):
        __slots__ = ["endpoint", "region", "bucket_name", "anonymous", "access_key"]
        ENDPOINT_FIELD_NUMBER: _ClassVar[int]
        REGION_FIELD_NUMBER: _ClassVar[int]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        ANONYMOUS_FIELD_NUMBER: _ClassVar[int]
        ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
        endpoint: str
        region: str
        bucket_name: str
        anonymous: TransferCredentialsAnonymous
        access_key: TransferCredentialsAccessKey
        def __init__(self, endpoint: _Optional[str] = ..., region: _Optional[str] = ..., bucket_name: _Optional[str] = ..., anonymous: _Optional[_Union[TransferCredentialsAnonymous, _Mapping]] = ..., access_key: _Optional[_Union[TransferCredentialsAccessKey, _Mapping]] = ...) -> None: ...
    class AzureBlobStorageProvider(_message.Message):
        __slots__ = ["endpoint", "container_name", "anonymous", "azure_storage_account"]
        ENDPOINT_FIELD_NUMBER: _ClassVar[int]
        CONTAINER_NAME_FIELD_NUMBER: _ClassVar[int]
        ANONYMOUS_FIELD_NUMBER: _ClassVar[int]
        AZURE_STORAGE_ACCOUNT_FIELD_NUMBER: _ClassVar[int]
        endpoint: str
        container_name: str
        anonymous: TransferCredentialsAnonymous
        azure_storage_account: TransferCredentialsAzureStorageAccount
        def __init__(self, endpoint: _Optional[str] = ..., container_name: _Optional[str] = ..., anonymous: _Optional[_Union[TransferCredentialsAnonymous, _Mapping]] = ..., azure_storage_account: _Optional[_Union[TransferCredentialsAzureStorageAccount, _Mapping]] = ...) -> None: ...
    NEBIUS_FIELD_NUMBER: _ClassVar[int]
    S3_COMPATIBLE_FIELD_NUMBER: _ClassVar[int]
    AZURE_BLOB_STORAGE_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    nebius: TransferSource.NebiusProvider
    s3_compatible: TransferSource.S3CompatibleProvider
    azure_blob_storage: TransferSource.AzureBlobStorageProvider
    prefix: str
    def __init__(self, nebius: _Optional[_Union[TransferSource.NebiusProvider, _Mapping]] = ..., s3_compatible: _Optional[_Union[TransferSource.S3CompatibleProvider, _Mapping]] = ..., azure_blob_storage: _Optional[_Union[TransferSource.AzureBlobStorageProvider, _Mapping]] = ..., prefix: _Optional[str] = ...) -> None: ...

class TransferDestination(_message.Message):
    __slots__ = ["nebius", "s3_compatible", "prefix"]
    class NebiusProvider(_message.Message):
        __slots__ = ["region", "bucket_name", "access_key"]
        REGION_FIELD_NUMBER: _ClassVar[int]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
        region: str
        bucket_name: str
        access_key: TransferCredentialsAccessKey
        def __init__(self, region: _Optional[str] = ..., bucket_name: _Optional[str] = ..., access_key: _Optional[_Union[TransferCredentialsAccessKey, _Mapping]] = ...) -> None: ...
    class S3CompatibleProvider(_message.Message):
        __slots__ = ["endpoint", "region", "bucket_name", "anonymous", "access_key"]
        ENDPOINT_FIELD_NUMBER: _ClassVar[int]
        REGION_FIELD_NUMBER: _ClassVar[int]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        ANONYMOUS_FIELD_NUMBER: _ClassVar[int]
        ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
        endpoint: str
        region: str
        bucket_name: str
        anonymous: TransferCredentialsAnonymous
        access_key: TransferCredentialsAccessKey
        def __init__(self, endpoint: _Optional[str] = ..., region: _Optional[str] = ..., bucket_name: _Optional[str] = ..., anonymous: _Optional[_Union[TransferCredentialsAnonymous, _Mapping]] = ..., access_key: _Optional[_Union[TransferCredentialsAccessKey, _Mapping]] = ...) -> None: ...
    NEBIUS_FIELD_NUMBER: _ClassVar[int]
    S3_COMPATIBLE_FIELD_NUMBER: _ClassVar[int]
    PREFIX_FIELD_NUMBER: _ClassVar[int]
    nebius: TransferDestination.NebiusProvider
    s3_compatible: TransferDestination.S3CompatibleProvider
    prefix: str
    def __init__(self, nebius: _Optional[_Union[TransferDestination.NebiusProvider, _Mapping]] = ..., s3_compatible: _Optional[_Union[TransferDestination.S3CompatibleProvider, _Mapping]] = ..., prefix: _Optional[str] = ...) -> None: ...

class TransferCredentialsAnonymous(_message.Message):
    __slots__ = []
    def __init__(self) -> None: ...

class TransferCredentialsAccessKey(_message.Message):
    __slots__ = ["access_key_id", "secret_access_key"]
    ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    SECRET_ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
    access_key_id: str
    secret_access_key: str
    def __init__(self, access_key_id: _Optional[str] = ..., secret_access_key: _Optional[str] = ...) -> None: ...

class TransferCredentialsAzureStorageAccount(_message.Message):
    __slots__ = ["account_name", "access_key"]
    ACCOUNT_NAME_FIELD_NUMBER: _ClassVar[int]
    ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
    account_name: str
    access_key: str
    def __init__(self, account_name: _Optional[str] = ..., access_key: _Optional[str] = ...) -> None: ...

class TransferStatus(_message.Message):
    __slots__ = ["state", "error", "suspension_state", "last_iteration"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[TransferStatus.State]
        ACTIVE: _ClassVar[TransferStatus.State]
        STOPPING: _ClassVar[TransferStatus.State]
        STOPPED: _ClassVar[TransferStatus.State]
        FAILING: _ClassVar[TransferStatus.State]
        FAILED: _ClassVar[TransferStatus.State]
        DELETING: _ClassVar[TransferStatus.State]
    STATE_UNSPECIFIED: TransferStatus.State
    ACTIVE: TransferStatus.State
    STOPPING: TransferStatus.State
    STOPPED: TransferStatus.State
    FAILING: TransferStatus.State
    FAILED: TransferStatus.State
    DELETING: TransferStatus.State
    class SuspensionState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        SUSPENSION_STATE_UNSPECIFIED: _ClassVar[TransferStatus.SuspensionState]
        NOT_SUSPENDED: _ClassVar[TransferStatus.SuspensionState]
        SUSPENDED: _ClassVar[TransferStatus.SuspensionState]
    SUSPENSION_STATE_UNSPECIFIED: TransferStatus.SuspensionState
    NOT_SUSPENDED: TransferStatus.SuspensionState
    SUSPENDED: TransferStatus.SuspensionState
    STATE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    SUSPENSION_STATE_FIELD_NUMBER: _ClassVar[int]
    LAST_ITERATION_FIELD_NUMBER: _ClassVar[int]
    state: TransferStatus.State
    error: TransferError
    suspension_state: TransferStatus.SuspensionState
    last_iteration: TransferIteration
    def __init__(self, state: _Optional[_Union[TransferStatus.State, str]] = ..., error: _Optional[_Union[TransferError, _Mapping]] = ..., suspension_state: _Optional[_Union[TransferStatus.SuspensionState, str]] = ..., last_iteration: _Optional[_Union[TransferIteration, _Mapping]] = ...) -> None: ...

class TransferIteration(_message.Message):
    __slots__ = ["sequence_number", "state", "error", "start_time", "end_time", "objects_transferred_count", "objects_transferred_size", "average_throughput_bytes"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[TransferIteration.State]
        IN_PROGRESS: _ClassVar[TransferIteration.State]
        COMPLETED: _ClassVar[TransferIteration.State]
        INTERRUPTED: _ClassVar[TransferIteration.State]
        FAILED: _ClassVar[TransferIteration.State]
    STATE_UNSPECIFIED: TransferIteration.State
    IN_PROGRESS: TransferIteration.State
    COMPLETED: TransferIteration.State
    INTERRUPTED: TransferIteration.State
    FAILED: TransferIteration.State
    SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    OBJECTS_TRANSFERRED_COUNT_FIELD_NUMBER: _ClassVar[int]
    OBJECTS_TRANSFERRED_SIZE_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_THROUGHPUT_BYTES_FIELD_NUMBER: _ClassVar[int]
    sequence_number: int
    state: TransferIteration.State
    error: TransferError
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    objects_transferred_count: int
    objects_transferred_size: int
    average_throughput_bytes: int
    def __init__(self, sequence_number: _Optional[int] = ..., state: _Optional[_Union[TransferIteration.State, str]] = ..., error: _Optional[_Union[TransferError, _Mapping]] = ..., start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., objects_transferred_count: _Optional[int] = ..., objects_transferred_size: _Optional[int] = ..., average_throughput_bytes: _Optional[int] = ...) -> None: ...

class TransferError(_message.Message):
    __slots__ = ["origin", "code", "message"]
    class Origin(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        ORIGIN_UNSPECIFIED: _ClassVar[TransferError.Origin]
        SOURCE: _ClassVar[TransferError.Origin]
        DESTINATION: _ClassVar[TransferError.Origin]
    ORIGIN_UNSPECIFIED: TransferError.Origin
    SOURCE: TransferError.Origin
    DESTINATION: TransferError.Origin
    ORIGIN_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    origin: TransferError.Origin
    code: str
    message: str
    def __init__(self, origin: _Optional[_Union[TransferError.Origin, str]] = ..., code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...
