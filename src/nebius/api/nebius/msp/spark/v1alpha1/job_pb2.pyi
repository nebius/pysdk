from nebius.api.buf.validate import validate_pb2 as _validate_pb2
from nebius.api.nebius import annotations_pb2 as _annotations_pb2
from nebius.api.nebius.common.v1 import metadata_pb2 as _metadata_pb2
from nebius.api.nebius.msp.spark.v1alpha1 import common_pb2 as _common_pb2
from nebius.api.nebius.msp.spark.v1alpha1 import preset_pb2 as _preset_pb2
from nebius.api.nebius.msp.v1alpha1 import cluster_pb2 as _cluster_pb2
from nebius.api.nebius.msp.v1alpha1.resource import template_pb2 as _template_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class JobResultCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    JOB_RESULT_CODE_UNSPECIFIED: _ClassVar[JobResultCode]
    SUCCEEDED: _ClassVar[JobResultCode]
    ERROR: _ClassVar[JobResultCode]
JOB_RESULT_CODE_UNSPECIFIED: JobResultCode
SUCCEEDED: JobResultCode
ERROR: JobResultCode

class Job(_message.Message):
    __slots__ = ["metadata", "spec", "status"]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    SPEC_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    metadata: _metadata_pb2.ResourceMetadata
    spec: JobSpec
    status: JobStatus
    def __init__(self, metadata: _Optional[_Union[_metadata_pb2.ResourceMetadata, _Mapping]] = ..., spec: _Optional[_Union[JobSpec, _Mapping]] = ..., status: _Optional[_Union[JobStatus, _Mapping]] = ...) -> None: ...

class JobSpec(_message.Message):
    __slots__ = ["description", "application_file_uri", "driver", "executor", "spark_version", "application_args", "file_uris", "jar_uris", "packages", "spark_conf", "python", "java"]
    class SparkConfEntry(_message.Message):
        __slots__ = ["key", "value"]
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    APPLICATION_FILE_URI_FIELD_NUMBER: _ClassVar[int]
    DRIVER_FIELD_NUMBER: _ClassVar[int]
    EXECUTOR_FIELD_NUMBER: _ClassVar[int]
    SPARK_VERSION_FIELD_NUMBER: _ClassVar[int]
    APPLICATION_ARGS_FIELD_NUMBER: _ClassVar[int]
    FILE_URIS_FIELD_NUMBER: _ClassVar[int]
    JAR_URIS_FIELD_NUMBER: _ClassVar[int]
    PACKAGES_FIELD_NUMBER: _ClassVar[int]
    SPARK_CONF_FIELD_NUMBER: _ClassVar[int]
    PYTHON_FIELD_NUMBER: _ClassVar[int]
    JAVA_FIELD_NUMBER: _ClassVar[int]
    description: str
    application_file_uri: str
    driver: _preset_pb2.DriverTemplateSpec
    executor: _preset_pb2.ExecutorTemplateSpec
    spark_version: str
    application_args: _containers.RepeatedScalarFieldContainer[str]
    file_uris: _containers.RepeatedScalarFieldContainer[str]
    jar_uris: _containers.RepeatedScalarFieldContainer[str]
    packages: _containers.RepeatedScalarFieldContainer[str]
    spark_conf: _containers.ScalarMap[str, str]
    python: _common_pb2.PythonConfig
    java: _common_pb2.JavaConfig
    def __init__(self, description: _Optional[str] = ..., application_file_uri: _Optional[str] = ..., driver: _Optional[_Union[_preset_pb2.DriverTemplateSpec, _Mapping]] = ..., executor: _Optional[_Union[_preset_pb2.ExecutorTemplateSpec, _Mapping]] = ..., spark_version: _Optional[str] = ..., application_args: _Optional[_Iterable[str]] = ..., file_uris: _Optional[_Iterable[str]] = ..., jar_uris: _Optional[_Iterable[str]] = ..., packages: _Optional[_Iterable[str]] = ..., spark_conf: _Optional[_Mapping[str, str]] = ..., python: _Optional[_Union[_common_pb2.PythonConfig, _Mapping]] = ..., java: _Optional[_Union[_common_pb2.JavaConfig, _Mapping]] = ...) -> None: ...

class JobResultDetails(_message.Message):
    __slots__ = ["code"]
    CODE_FIELD_NUMBER: _ClassVar[int]
    code: JobResultCode
    def __init__(self, code: _Optional[_Union[JobResultCode, str]] = ...) -> None: ...

class JobStatus(_message.Message):
    __slots__ = ["phase", "state", "driver_endpoint", "driver_preset_details", "executor_preset_details", "result_details"]
    PHASE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    DRIVER_ENDPOINT_FIELD_NUMBER: _ClassVar[int]
    DRIVER_PRESET_DETAILS_FIELD_NUMBER: _ClassVar[int]
    EXECUTOR_PRESET_DETAILS_FIELD_NUMBER: _ClassVar[int]
    RESULT_DETAILS_FIELD_NUMBER: _ClassVar[int]
    phase: _cluster_pb2.ClusterStatus.Phase
    state: _cluster_pb2.ClusterStatus.State
    driver_endpoint: str
    driver_preset_details: _template_pb2.PresetDetails
    executor_preset_details: _template_pb2.PresetDetails
    result_details: JobResultDetails
    def __init__(self, phase: _Optional[_Union[_cluster_pb2.ClusterStatus.Phase, str]] = ..., state: _Optional[_Union[_cluster_pb2.ClusterStatus.State, str]] = ..., driver_endpoint: _Optional[str] = ..., driver_preset_details: _Optional[_Union[_template_pb2.PresetDetails, _Mapping]] = ..., executor_preset_details: _Optional[_Union[_template_pb2.PresetDetails, _Mapping]] = ..., result_details: _Optional[_Union[JobResultDetails, _Mapping]] = ...) -> None: ...
