from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class ExportFormat(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = []
    EXPORT_FORMAT_UNSPECIFIED: _ClassVar[ExportFormat]
    EXPORT_FORMAT_FOCUS_1_2_CSV: _ClassVar[ExportFormat]
    EXPORT_FORMAT_CONSUMPTION_BREAKDOWN_PDF: _ClassVar[ExportFormat]
EXPORT_FORMAT_UNSPECIFIED: ExportFormat
EXPORT_FORMAT_FOCUS_1_2_CSV: ExportFormat
EXPORT_FORMAT_CONSUMPTION_BREAKDOWN_PDF: ExportFormat
