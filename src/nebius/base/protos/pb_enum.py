from enum import (
    IntEnum,
)
from typing import Any

import google.protobuf.descriptor as pb

from nebius.base.protos.descriptor import DescriptorWrap


class Enum(IntEnum):
    @classmethod
    def get_descriptor(cls) -> pb.EnumDescriptor:
        desc: Any = getattr(cls, "#descriptor", None)
        if desc is None:
            for val in cls.__dict__.values():
                if isinstance(val, DescriptorWrap):
                    desc = val()  # type: ignore[unused-ignore]
        if isinstance(desc, pb.EnumDescriptor):
            return desc
        raise ValueError(f"Descriptor not found in {cls.__name__}.")
