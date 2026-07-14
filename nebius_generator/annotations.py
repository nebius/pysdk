"""Annotation helpers for compiler descriptor processing."""

from datetime import date
from enum import IntEnum

import google.protobuf.descriptor_pb2 as pb
from google.protobuf import descriptor as descriptor

from ._bootstrap import annotations_pb2
from ._bootstrap.annotations_pb2 import (
    DeprecationDetails as DeprecationDetailsMessage,
)
from ._bootstrap.annotations_pb2 import field_behavior as fb_descriptor
from .descriptors import Descriptor, Field


class FieldBehavior(IntEnum):
    """Generator-local field behavior values."""

    FIELD_BEHAVIOR_UNSPECIFIED = annotations_pb2.FIELD_BEHAVIOR_UNSPECIFIED
    IMMUTABLE = annotations_pb2.IMMUTABLE
    IDENTIFIER = annotations_pb2.IDENTIFIER
    INPUT_ONLY = annotations_pb2.INPUT_ONLY
    OUTPUT_ONLY = annotations_pb2.OUTPUT_ONLY
    MEANINGFUL_EMPTY_VALUE = annotations_pb2.MEANINGFUL_EMPTY_VALUE
    NON_EMPTY_DEFAULT = annotations_pb2.NON_EMPTY_DEFAULT


class MethodBehavior(IntEnum):
    """Generator-local method behavior values."""

    METHOD_BEHAVIOR_UNSPECIFIED = annotations_pb2.METHOD_BEHAVIOR_UNSPECIFIED
    METHOD_UPDATER = annotations_pb2.METHOD_UPDATER
    METHOD_PAGINATED = annotations_pb2.METHOD_PAGINATED
    METHOD_WITHOUT_GET = annotations_pb2.METHOD_WITHOUT_GET


_cache = dict[str, set[FieldBehavior]]()


def field_behavior(field: Field) -> set[FieldBehavior]:
    """Return the set of field behaviors for a field descriptor.

    :param field: Compiler :class:`Field` wrapper.
    :returns: Set of :class:`FieldBehavior` values.
    """
    if field.full_type_name in _cache:
        return _cache[field.full_type_name]
    fb_array = field.descriptor.options.Extensions[fb_descriptor]  # type: ignore
    ret = set[FieldBehavior]()
    for fb in fb_array:  # type: ignore[unused-ignore]
        ret.add(FieldBehavior(fb))
    _cache[field.full_type_name] = ret
    return ret


class DeprecationDetails:
    """Wrapper for deprecation details with convenience formatting."""

    def __init__(self, message: DeprecationDetailsMessage) -> None:
        self._message = message

    @property
    def description(self) -> str:
        return str(self._message.description)

    @property
    def effective_at_date(self) -> date | None:
        """Return the effective deprecation date or ``None``."""
        if self._message.effective_at == "":
            return None
        return date.fromisoformat(self._message.effective_at)

    def __str__(self) -> str:
        """Return a human-readable summary of deprecation details."""
        res = list[str]()
        if self.effective_at_date is not None:
            res.append(f"Supported until {self.effective_at_date:%x}.")
        if self.description != "":
            desc = self.description[0:1].upper() + self.description[1:]
            if not self.description.endswith("."):
                desc += "."
            res.append(desc)
        return " ".join(res)


pb_descriptors = (
    pb.DescriptorProto
    | pb.FieldDescriptorProto
    | pb.EnumDescriptorProto
    | pb.EnumValueDescriptorProto
    | pb.ServiceDescriptorProto
    | pb.MethodDescriptorProto
    | pb.FileDescriptorProto
)


def get_deprecation_details(
    descriptor: Descriptor | pb_descriptors,
    extension: descriptor.FieldDescriptor,
) -> DeprecationDetails | None:
    """Extract deprecation details from a descriptor extension.

    :param descriptor: Compiler descriptor or protobuf descriptor proto.
    :param extension: Extension field descriptor containing deprecation details.
    :returns: :class:`DeprecationDetails` or ``None`` when not set.
    """
    if isinstance(descriptor, Descriptor):
        descriptor = descriptor.descriptor  # type: ignore
    details = DeprecationDetails(
        descriptor.options.Extensions[extension]  # type: ignore
    )
    if details.effective_at_date is None:
        return None

    return details
