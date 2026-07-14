"""Enum base class with descriptor lookup support."""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING, Any, ClassVar

import google.protobuf.descriptor as pb

from nebius.base.protos.descriptor import DescriptorWrap

if TYPE_CHECKING:
    from .registry import Registry


class Enum(IntEnum):
    """IntEnum subclass that can resolve its protobuf descriptor."""

    __PROTO_FULL_NAME__: ClassVar[str]
    __REGISTRY__: ClassVar[Registry | None] = None
    __PROTO_DESCRIPTOR__: ClassVar[Any] = None
    __PB2_DESCRIPTOR__: ClassVar[Any] = None

    @classmethod
    def _missing_(cls, value: object) -> "Enum" | None:
        """Represent unknown open-enum numbers without losing their value."""
        if not isinstance(value, int):
            return None
        member = int.__new__(cls, value)
        member._name_ = f"UNRECOGNIZED_{value}"
        member._value_ = value
        return member

    @classmethod
    def get_descriptor(cls) -> Any:
        """Return the protobuf ``EnumDescriptor`` for this enum.

        :returns: Protobuf enum descriptor.
        :raises ValueError: If no descriptor is attached to the enum class.
        """
        desc: Any = cls.__PROTO_DESCRIPTOR__ or cls.__PB2_DESCRIPTOR__
        if desc is not None:
            return desc() if callable(desc) else desc
        desc = getattr(cls, "#descriptor", None)
        if desc is None:
            for val in cls.__dict__.values():
                if isinstance(val, DescriptorWrap):
                    desc = val()  # type: ignore[unused-ignore]
        if isinstance(desc, pb.EnumDescriptor):
            return desc
        raise ValueError(f"Descriptor not found in {cls.__name__}.")
