from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import duration_pb2 as _duration_pb2
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
    __slots__ = ["source", "destination", "after_one_iteration", "after_n_empty_iterations", "infinite", "inter_iteration_interval", "overwrite_strategy"]
    class OverwriteStrategy(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        OVERWRITE_STRATEGY_UNSPECIFIED: _ClassVar[TransferSpec.OverwriteStrategy]
        NEVER: _ClassVar[TransferSpec.OverwriteStrategy]
        IF_NEWER: _ClassVar[TransferSpec.OverwriteStrategy]
        ALWAYS: _ClassVar[TransferSpec.OverwriteStrategy]
    OVERWRITE_STRATEGY_UNSPECIFIED: TransferSpec.OverwriteStrategy
    NEVER: TransferSpec.OverwriteStrategy
    IF_NEWER: TransferSpec.OverwriteStrategy
    ALWAYS: TransferSpec.OverwriteStrategy
    class SourceBucket(_message.Message):
        __slots__ = ["endpoint", "bucket_name", "region", "credentials", "limiters"]
        ENDPOINT_FIELD_NUMBER: _ClassVar[int]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        REGION_FIELD_NUMBER: _ClassVar[int]
        CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
        LIMITERS_FIELD_NUMBER: _ClassVar[int]
        endpoint: str
        bucket_name: str
        region: str
        credentials: TransferSpec.BucketCredentials
        limiters: TransferSpec.Limiters
        def __init__(self, endpoint: _Optional[str] = ..., bucket_name: _Optional[str] = ..., region: _Optional[str] = ..., credentials: _Optional[_Union[TransferSpec.BucketCredentials, _Mapping]] = ..., limiters: _Optional[_Union[TransferSpec.Limiters, _Mapping]] = ...) -> None: ...
    class DestinationBucket(_message.Message):
        __slots__ = ["bucket_name", "credentials"]
        BUCKET_NAME_FIELD_NUMBER: _ClassVar[int]
        CREDENTIALS_FIELD_NUMBER: _ClassVar[int]
        bucket_name: str
        credentials: TransferSpec.BucketCredentials
        def __init__(self, bucket_name: _Optional[str] = ..., credentials: _Optional[_Union[TransferSpec.BucketCredentials, _Mapping]] = ...) -> None: ...
    class BucketCredentials(_message.Message):
        __slots__ = ["anonymous", "access_key", "azure_access_key"]
        class CredentialsAnonymous(_message.Message):
            __slots__ = []
            def __init__(self) -> None: ...
        class CredentialsAccessKey(_message.Message):
            __slots__ = ["access_key_id", "secret_access_key"]
            ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
            SECRET_ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
            access_key_id: str
            secret_access_key: str
            def __init__(self, access_key_id: _Optional[str] = ..., secret_access_key: _Optional[str] = ...) -> None: ...
        class AzureAccessKey(_message.Message):
            __slots__ = ["account_name", "access_key"]
            ACCOUNT_NAME_FIELD_NUMBER: _ClassVar[int]
            ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
            account_name: str
            access_key: str
            def __init__(self, account_name: _Optional[str] = ..., access_key: _Optional[str] = ...) -> None: ...
        ANONYMOUS_FIELD_NUMBER: _ClassVar[int]
        ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
        AZURE_ACCESS_KEY_FIELD_NUMBER: _ClassVar[int]
        anonymous: TransferSpec.BucketCredentials.CredentialsAnonymous
        access_key: TransferSpec.BucketCredentials.CredentialsAccessKey
        azure_access_key: TransferSpec.BucketCredentials.AzureAccessKey
        def __init__(self, anonymous: _Optional[_Union[TransferSpec.BucketCredentials.CredentialsAnonymous, _Mapping]] = ..., access_key: _Optional[_Union[TransferSpec.BucketCredentials.CredentialsAccessKey, _Mapping]] = ..., azure_access_key: _Optional[_Union[TransferSpec.BucketCredentials.AzureAccessKey, _Mapping]] = ...) -> None: ...
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
    AFTER_ONE_ITERATION_FIELD_NUMBER: _ClassVar[int]
    AFTER_N_EMPTY_ITERATIONS_FIELD_NUMBER: _ClassVar[int]
    INFINITE_FIELD_NUMBER: _ClassVar[int]
    INTER_ITERATION_INTERVAL_FIELD_NUMBER: _ClassVar[int]
    OVERWRITE_STRATEGY_FIELD_NUMBER: _ClassVar[int]
    source: TransferSpec.SourceBucket
    destination: TransferSpec.DestinationBucket
    after_one_iteration: TransferSpec.StopConditionAfterOneIteration
    after_n_empty_iterations: TransferSpec.StopConditionAfterNEmptyIterations
    infinite: TransferSpec.StopConditionInfinite
    inter_iteration_interval: _duration_pb2.Duration
    overwrite_strategy: TransferSpec.OverwriteStrategy
    def __init__(self, source: _Optional[_Union[TransferSpec.SourceBucket, _Mapping]] = ..., destination: _Optional[_Union[TransferSpec.DestinationBucket, _Mapping]] = ..., after_one_iteration: _Optional[_Union[TransferSpec.StopConditionAfterOneIteration, _Mapping]] = ..., after_n_empty_iterations: _Optional[_Union[TransferSpec.StopConditionAfterNEmptyIterations, _Mapping]] = ..., infinite: _Optional[_Union[TransferSpec.StopConditionInfinite, _Mapping]] = ..., inter_iteration_interval: _Optional[_Union[_duration_pb2.Duration, _Mapping]] = ..., overwrite_strategy: _Optional[_Union[TransferSpec.OverwriteStrategy, str]] = ...) -> None: ...

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
    STATE_UNSPECIFIED: TransferStatus.State
    ACTIVE: TransferStatus.State
    STOPPING: TransferStatus.State
    STOPPED: TransferStatus.State
    FAILING: TransferStatus.State
    FAILED: TransferStatus.State
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
    error: str
    suspension_state: TransferStatus.SuspensionState
    last_iteration: TransferIteration
    def __init__(self, state: _Optional[_Union[TransferStatus.State, str]] = ..., error: _Optional[str] = ..., suspension_state: _Optional[_Union[TransferStatus.SuspensionState, str]] = ..., last_iteration: _Optional[_Union[TransferIteration, _Mapping]] = ...) -> None: ...

class TransferIteration(_message.Message):
    __slots__ = ["sequence_number", "state", "error", "start_time", "end_time", "objects_discovered_count", "objects_migrated_count", "objects_skipped_count", "objects_migrated_size", "average_throughput_bytes"]
    class State(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = []
        STATE_UNSPECIFIED: _ClassVar[TransferIteration.State]
        IN_PROGRESS: _ClassVar[TransferIteration.State]
        COMPLETED: _ClassVar[TransferIteration.State]
        STOPPED: _ClassVar[TransferIteration.State]
        FAILED: _ClassVar[TransferIteration.State]
    STATE_UNSPECIFIED: TransferIteration.State
    IN_PROGRESS: TransferIteration.State
    COMPLETED: TransferIteration.State
    STOPPED: TransferIteration.State
    FAILED: TransferIteration.State
    SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    END_TIME_FIELD_NUMBER: _ClassVar[int]
    OBJECTS_DISCOVERED_COUNT_FIELD_NUMBER: _ClassVar[int]
    OBJECTS_MIGRATED_COUNT_FIELD_NUMBER: _ClassVar[int]
    OBJECTS_SKIPPED_COUNT_FIELD_NUMBER: _ClassVar[int]
    OBJECTS_MIGRATED_SIZE_FIELD_NUMBER: _ClassVar[int]
    AVERAGE_THROUGHPUT_BYTES_FIELD_NUMBER: _ClassVar[int]
    sequence_number: int
    state: TransferIteration.State
    error: str
    start_time: _timestamp_pb2.Timestamp
    end_time: _timestamp_pb2.Timestamp
    objects_discovered_count: int
    objects_migrated_count: int
    objects_skipped_count: int
    objects_migrated_size: int
    average_throughput_bytes: int
    def __init__(self, sequence_number: _Optional[int] = ..., state: _Optional[_Union[TransferIteration.State, str]] = ..., error: _Optional[str] = ..., start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., end_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., objects_discovered_count: _Optional[int] = ..., objects_migrated_count: _Optional[int] = ..., objects_skipped_count: _Optional[int] = ..., objects_migrated_size: _Optional[int] = ..., average_throughput_bytes: _Optional[int] = ...) -> None: ...
