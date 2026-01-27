"""Enum base class with descriptor lookup support."""

from enum import IntEnum
from typing import Any

import google.protobuf.descriptor as pb

from nebius.base.protos.descriptor import DescriptorWrap


class Enum(IntEnum):
    """IntEnum subclass that can resolve its protobuf descriptor."""

    @classmethod
    def get_descriptor(cls) -> pb.EnumDescriptor:
        """Return the protobuf ``EnumDescriptor`` for this enum.

        :returns: Protobuf enum descriptor.
        :raises ValueError: If no descriptor is attached to the enum class.
        """
        desc: Any = getattr(cls, "#descriptor", None)
        if desc is None:
            for val in cls.__dict__.values():
                if isinstance(val, DescriptorWrap):
                    desc = val()  # type: ignore[unused-ignore]
        if isinstance(desc, pb.EnumDescriptor):
            return desc
        raise ValueError(f"Descriptor not found in {cls.__name__}.")
