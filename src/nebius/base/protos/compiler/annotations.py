"""Annotation helpers for compiler descriptor processing."""

from datetime import date

import google.protobuf.descriptor_pb2 as pb
from google.protobuf import descriptor as descriptor

from nebius.api.nebius import DeprecationDetails as DeprecationDetailsMessage
from nebius.api.nebius import FieldBehavior
from nebius.api.nebius import field_behavior as fb_descriptor
from nebius.base.protos.compiler.descriptors import Descriptor, Field

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


class DeprecationDetails(DeprecationDetailsMessage):
    """Wrapper for deprecation details with convenience formatting."""

    @property
    def effective_at_date(self) -> date | None:
        """Return the effective deprecation date or ``None``."""
        if super().effective_at == "":
            return None
        return date.fromisoformat(super().effective_at)

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
