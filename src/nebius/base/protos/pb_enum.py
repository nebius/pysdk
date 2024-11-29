# type: ignore
from __future__ import annotations

from enum import (
    EnumMeta,
    IntEnum,
)
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Optional,
    Tuple,
)

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        Mapping,
    )

    from typing_extensions import (
        Never,
        Self,
    )

from google.protobuf.descriptor import EnumDescriptor

from .descriptor import DescriptorWrap


def _is_descriptor(obj: object) -> bool:
    return isinstance(obj, EnumDescriptor) or isinstance(obj, DescriptorWrap)


class EnumType(EnumMeta if TYPE_CHECKING else type):
    _value_map_: Mapping[int, Enum]
    _member_map_: Mapping[str, Enum]

    def __new__(
        mcs,  # noqa: N804, N805
        name: str,
        bases: Tuple[type, ...],
        namespace: Dict[str, Any],
    ) -> Self:
        value_map = {}
        member_map = {}
        print(f"1, {bases}")

        mod_bases = tuple(
            dict.fromkeys(
                [base.__class__ for base in bases if base.__class__ is not type]
                + [EnumType, type]
            )
        )

        new_mcs = type(
            f"{name}Type",
            mod_bases,  # reorder the bases so EnumType and type are last to avoid
            # conflicts
            {"_value_map_": value_map, "_member_map_": member_map},
        )
        print(f"2 {new_mcs} {mod_bases}")
        descriptor = None
        for name_, value in namespace.items():
            if _is_descriptor(value):
                descriptor = value
                break

        members = {
            name: value
            for name, value in namespace.items()
            if not _is_descriptor(value) and not name.startswith("__")
        }

        new_namespace = {
            key: value for key, value in namespace.items() if key not in members
        }

        new_namespace["#descriptor"] = descriptor
        new_namespace["value"] = 0
        new_namespace["name"] = "None"

        print("3", flush=True)
        cls = type.__new__(
            new_mcs,
            name,
            bases,
            new_namespace,
        )
        # this allows us to disallow member access from other members as
        # members become proper class variables

        print(f"4 {cls} {name} {bases} {new_namespace}", flush=True)
        for name, value in members.items():
            member = value_map.get(value)
            if member is None:
                print(f"4.5 value {value} name {name}", flush=True)
                member = cls.__new__(cls, name=name, value=value)  # type: ignore
                value_map[value] = member
            member_map[name] = member
            type.__setattr__(new_mcs, name, member)

        print("5", flush=True)
        return cls

    if not TYPE_CHECKING:

        def __call__(cls, value: int) -> Enum:  # noqa: N804, N805
            print("6", flush=True)
            try:
                return cls._value_map_[value]
            except (KeyError, TypeError):
                raise ValueError(f"{value!r} is not a valid {cls.__name__}") from None

        def __iter__(cls) -> Generator[Enum, None, None]:  # noqa: N804, N805
            yield from cls._member_map_.values()

        def __reversed__(cls) -> Generator[Enum, None, None]:  # noqa: N804, N805
            yield from reversed(cls._member_map_.values())

        def __getitem__(cls, key: str) -> Enum:  # noqa: N804, N805
            return cls._member_map_[key]

        @property
        def __members__(cls) -> MappingProxyType[str, Enum]:  # noqa: N804, N805
            return MappingProxyType(cls._member_map_)

    def __repr__(cls) -> str:  # noqa: N804, N805
        return f"<enum {cls.__name__!r}>"

    def __len__(cls) -> int:  # noqa: N804, N805
        return len(cls._member_map_)

    def __setattr__(cls, name: str, value: Any) -> Never:  # noqa: N804, N805
        raise AttributeError(f"{cls.__name__}: cannot reassign Enum members.")

    def __delattr__(cls, name: str) -> Never:  # noqa: N804, N805
        raise AttributeError(f"{cls.__name__}: cannot delete Enum members.")

    def __contains__(cls, member: object) -> bool:  # noqa: N804, N805
        return isinstance(member, cls) and member.name in cls._member_map_


class Enum(IntEnum if TYPE_CHECKING else int, metaclass=EnumType):
    """
    The base class for protobuf enumerations, all generated enumerations will
    inherit from this. Emulates `enum.IntEnum`.
    """

    name: Optional[str]
    value: int

    if not TYPE_CHECKING:

        def __new__(cls, *, name: Optional[str], value: int) -> Self:
            print(f"7 {cls} {cls.__class__}")
            self = value
            setattr(self, "name", name)
            setattr(self, "value", value)
            return self

    def __str__(self) -> str:
        return self.name or "None"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    def __setattr__(self, key: str, value: Any) -> Never:
        raise AttributeError(
            f"{self.__class__.__name__} Cannot reassign a member's attributes."
        )

    def __delattr__(self, item: Any) -> Never:
        raise AttributeError(
            f"{self.__class__.__name__} Cannot delete a member's attributes."
        )

    def __copy__(self) -> Self:
        return self

    def __deepcopy__(self, memo: Any) -> Self:
        return self

    @classmethod
    def get_descriptor(cls) -> EnumDescriptor:
        descriptor = getattr(cls, "#descriptor")
        if descriptor is None:
            ValueError("No descriptor provided.")
        if isinstance(descriptor, DescriptorWrap):
            descriptor = descriptor()
        if isinstance(descriptor, EnumDescriptor):
            return descriptor
        ValueError(f"Wrong descriptor type {type(descriptor)} provided.")

    @classmethod
    def try_value(cls, value: int = 0) -> Self:
        """Return the value which corresponds to the value.

        Parameters
        -----------
        value: :class:`int`
            The value of the enum member to get.

        Returns
        -------
        :class:`Enum`
            The corresponding member or a new instance of the enum if
            ``value`` isn't actually a member.
        """
        try:
            return cls._value_map_[value]
        except (KeyError, TypeError):
            return cls.__new__(cls, name=None, value=value)

    @classmethod
    def from_string(cls, name: str) -> Self:
        """Return the value which corresponds to the string name.

        Parameters
        -----------
        name: :class:`str`
            The name of the enum member to get.

        Raises
        -------
        :exc:`ValueError`
            The member was not found in the Enum.
        """
        try:
            return cls._member_map_[name]
        except KeyError as e:
            raise ValueError(f"Unknown value {name} for enum {cls.__name__}") from e
