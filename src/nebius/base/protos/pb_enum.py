"""Enum base class with descriptor lookup support."""

from enum import IntEnum

import google.protobuf.descriptor as pb


class Enum(IntEnum):
    """IntEnum subclass that can resolve its protobuf descriptor."""

    @classmethod
    def get_descriptor(cls) -> pb.EnumDescriptor:
        """Return the protobuf ``EnumDescriptor`` for this enum.

        :returns: Protobuf enum descriptor.
        :raises ValueError: If no descriptor is attached to the enum class.
        """
        desc = getattr(cls, "__PROTO_DESCRIPTOR__", None)
        if isinstance(desc, pb.EnumDescriptor):
            return desc
        raise ValueError(f"Descriptor not found in {cls.__name__}.")
