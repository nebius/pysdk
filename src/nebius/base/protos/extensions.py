"""Namespace-owned protobuf extension descriptors and value storage."""

from __future__ import annotations

from collections.abc import Callable, Iterable, MutableSequence
from dataclasses import dataclass
from typing import Any, Generic, Iterator, TypeVar, cast, overload

from .codec import ValueCodec
from .wire import WIRE_LENGTH_DELIMITED, BinaryReader, BinaryWriter

T = TypeVar("T")
E = TypeVar("E")


class RepeatedValues(MutableSequence[T], Generic[T]):
    """Stable repeated-extension container with protobuf setter semantics."""

    def __init__(self, codec: ValueCodec[T], on_mutation: Callable[[], None]) -> None:
        self._codec = codec
        self._items: list[T] = []
        self._on_mutation = on_mutation

    def _prepare(self, value: object) -> T:
        owned = self._codec.copy(self._codec.normalize(value))
        if self._codec.bind_mutation is not None:
            self._codec.bind_mutation(owned, self._on_mutation)
        return owned

    def _detach(self, value: T) -> None:
        if self._codec.bind_mutation is not None:
            self._codec.bind_mutation(value, lambda: None)

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> list[T]: ...

    def __getitem__(self, index: int | slice) -> T | list[T]:
        return self._items[index]

    @overload
    def __setitem__(self, index: int, value: T) -> None: ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[T]) -> None: ...

    def __setitem__(self, index: int | slice, value: T | Iterable[T]) -> None:
        if isinstance(index, slice):
            if not isinstance(value, Iterable):
                raise TypeError("slice assignment requires an iterable")
            prepared = [self._prepare(item) for item in value]
            replacement = self._items.copy()
            replacement[index] = prepared
            for previous in self._items[index]:
                self._detach(previous)
            self._items = replacement
        else:
            prepared_item = self._prepare(value)
            self._detach(self._items[index])
            self._items[index] = prepared_item
        self._on_mutation()

    def __delitem__(self, index: int | slice) -> None:
        if isinstance(index, slice):
            for item in self._items[index]:
                self._detach(item)
        else:
            self._detach(self._items[index])
        del self._items[index]
        self._on_mutation()

    def __len__(self) -> int:
        return len(self._items)

    def insert(self, index: int, value: T) -> None:
        self._items.insert(index, self._prepare(value))
        self._on_mutation()

    def extend(self, values: Iterable[T]) -> None:
        prepared = [self._prepare(value) for value in values]
        if prepared:
            self._items.extend(prepared)
            self._on_mutation()

    def replace(self, values: Iterable[T]) -> None:
        prepared = [self._prepare(value) for value in values]
        for previous in self._items:
            self._detach(previous)
        self._items[:] = prepared
        self._on_mutation()

    def clear(self) -> None:
        if self._items:
            for previous in self._items:
                self._detach(previous)
            self._items.clear()
            self._on_mutation()

    def reverse(self) -> None:
        if len(self._items) > 1:
            self._items.reverse()
            self._on_mutation()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RepeatedValues):
            return self._items == other._items
        if isinstance(other, list):
            return self._items == other
        return False

    def __repr__(self) -> str:
        return repr(self._items)


@dataclass(frozen=True)
class ExtensionDecodeResult:
    """Outcome of attempting to consume one extension wire occurrence."""

    consumed: bool
    unknown_fields: tuple[bytes, ...] = ()


@dataclass(frozen=True, eq=False)
class Extension(Generic[T]):
    """Typed declaration of one protobuf extension field."""

    registry: ExtensionRegistry
    full_name: str
    extendee: str
    number: int
    value_codec: ValueCodec[Any]
    default_factory: Callable[[], T]
    repeated: bool = False
    packed: bool = False
    public: bool = True


class ExtensionRegistry:
    """Frozen extension lookup scoped to one generated namespace."""

    def __init__(self) -> None:
        self._by_number: dict[tuple[str, int], Extension[Any]] = {}
        self._by_name: dict[str, Extension[Any]] = {}
        self._ranges: dict[str, tuple[tuple[int, int], ...]] = {}
        self._frozen = False

    def add_extendee(self, extendee: str, ranges: Iterable[tuple[int, int]]) -> None:
        if self._frozen:
            raise RuntimeError("extension registry is frozen")
        normalized = tuple(ranges)
        if any(start < 1 or end <= start for start, end in normalized):
            raise ValueError("invalid protobuf extension range")
        if extendee in self._ranges:
            raise ValueError("duplicate protobuf extension extendee")
        self._ranges[extendee] = normalized

    def register(self, extension: Extension[Any]) -> None:
        if self._frozen:
            raise RuntimeError("extension registry is frozen")
        if extension.registry is not self:
            raise ValueError("extension belongs to another registry")
        if extension.packed and (
            not extension.repeated or not extension.value_codec.packable
        ):
            raise ValueError("only repeated packable extensions may be packed")
        ranges = self._ranges.get(extension.extendee, ())
        if not any(start <= extension.number < end for start, end in ranges):
            raise ValueError("extension number is outside its extendee ranges")
        number_key = (extension.extendee, extension.number)
        if number_key in self._by_number or extension.full_name in self._by_name:
            raise ValueError("conflicting protobuf extension registration")
        self._by_number[number_key] = extension
        self._by_name[extension.full_name] = extension

    def freeze(self) -> None:
        self._frozen = True

    @property
    def frozen(self) -> bool:
        return self._frozen

    def by_number(self, extendee: str, number: int) -> Extension[Any] | None:
        return self._by_number.get((extendee, number))

    def by_name(self, full_name: str) -> Extension[Any] | None:
        return self._by_name.get(full_name)


class ExtensionValues:
    """Present typed extension values for one direct message instance."""

    def __init__(
        self,
        registry: ExtensionRegistry,
        extendee: str,
        on_mutation: Callable[[], None] | None = None,
    ) -> None:
        if not registry.frozen:
            raise RuntimeError("extension registry must be frozen before decoding")
        self._registry = registry
        self._extendee = extendee
        self._values: dict[Extension[Any], Any] = {}
        self._present: set[Extension[Any]] = set()
        self._on_mutation = on_mutation

    def _notify(self) -> None:
        if self._on_mutation is not None:
            self._on_mutation()

    def _mark_present(self, extension: Extension[Any]) -> None:
        self._present.add(extension)
        self._notify()

    def _repeated(self, extension: Extension[Any]) -> RepeatedValues[Any]:
        value = self._values.get(extension)
        if value is None:
            value = RepeatedValues(extension.value_codec, self._notify)
            self._values[extension] = value
        return cast(RepeatedValues[Any], value)

    def _bind_singular(self, extension: Extension[Any], value: Any) -> Any:
        bind_mutation = extension.value_codec.bind_mutation
        if bind_mutation is not None:
            bind_mutation(value, lambda: self._mark_present(extension))
        return value

    def _detach_singular(self, extension: Extension[Any]) -> None:
        value = self._values.get(extension)
        bind_mutation = extension.value_codec.bind_mutation
        if value is not None and bind_mutation is not None:
            bind_mutation(value, lambda: None)

    def _check(self, extension: Extension[Any]) -> None:
        if extension.registry is not self._registry:
            raise ValueError("extension belongs to another registry")
        if extension.extendee != self._extendee:
            raise ValueError("extension has the wrong extendee")
        if self._registry.by_number(self._extendee, extension.number) is not extension:
            raise ValueError("extension is not registered in this registry")

    @overload
    def get(self, extension: Extension[T]) -> T: ...

    @overload
    def get(self, extension: Extension[list[E]]) -> RepeatedValues[E]: ...

    def get(self, extension: Extension[Any]) -> Any:
        self._check(extension)
        if extension in self._values:
            return self._values[extension]
        if extension.repeated:
            return self._repeated(extension)
        value = extension.default_factory()
        if extension.value_codec.bind_mutation is not None:
            self._values[extension] = self._bind_singular(extension, value)
        return value

    def set(self, extension: Extension[T], value: T) -> None:
        self._check(extension)
        codec = extension.value_codec
        if extension.repeated:
            if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
                raise TypeError("repeated extension requires an iterable")
            self._repeated(extension).replace(value)
        else:
            owned = codec.copy(codec.normalize(value))
            self._detach_singular(extension)
            self._values[extension] = self._bind_singular(extension, owned)
            self._mark_present(extension)

    def has(self, extension: Extension[Any]) -> bool:
        self._check(extension)
        if extension.repeated:
            return bool(self._values.get(extension))
        return extension in self._present

    def clear(self, extension: Extension[Any]) -> None:
        self._check(extension)
        if extension.repeated:
            value = self._values.get(extension)
            if value is not None:
                cast(RepeatedValues[Any], value).clear()
            return
        changed = extension in self._present
        self._detach_singular(extension)
        self._values.pop(extension, None)
        self._present.discard(extension)
        if changed:
            self._notify()

    def clear_all(self) -> None:
        """Clear typed values while retaining stable repeated containers."""
        for extension in tuple(self._values):
            if extension.repeated:
                self._repeated(extension).clear()
            else:
                self._detach_singular(extension)
                self._values.pop(extension, None)
        self._present.clear()

    def find_initialization_errors(self) -> list[str]:
        """Return required-field paths from present message extension values."""
        errors: list[str] = []
        for extension, value in sorted(
            self._values.items(), key=lambda item: item[0].number
        ):
            if extension.value_codec.bind_mutation is None:
                continue
            name = extension.full_name.rsplit(".", 1)[-1]
            if extension.repeated:
                for index, item in enumerate(cast(RepeatedValues[Any], value)):
                    finder = getattr(item, "FindInitializationErrors", None)
                    if callable(finder):
                        errors.extend(
                            f"{name}[{index}].{nested}" for nested in finder()
                        )
            elif extension in self._present:
                finder = getattr(value, "FindInitializationErrors", None)
                if callable(finder):
                    errors.extend(f"{name}.{nested}" for nested in finder())
        return errors

    def present_items(self) -> Iterator[tuple[Extension[Any], Any]]:
        """Iterate present extension values in field-number order."""
        for extension, value in sorted(
            self._values.items(), key=lambda item: item[0].number
        ):
            if extension.repeated:
                if value:
                    yield extension, value
            elif extension in self._present:
                yield extension, value

    def try_decode(
        self,
        extension: Extension[Any],
        reader: BinaryReader,
        wire_type: int,
        tag_start: int,
    ) -> ExtensionDecodeResult:
        self._check(extension)
        codec = extension.value_codec
        if extension.repeated and codec.packable and wire_type == WIRE_LENGTH_DELIMITED:
            decoded = reader.read_packed(lambda: codec.read(reader))
            values = self._repeated(extension)
            unknown: list[bytes] = []
            for value in decoded:
                if (
                    codec.closed_enum
                    and codec.enum_values is not None
                    and value not in codec.enum_values
                ):
                    writer = BinaryWriter()
                    writer.write_tag(extension.number, codec.wire_type)
                    writer.write_varint(value & 0xFFFFFFFF)
                    unknown.append(writer.to_bytes())
                else:
                    values.append(codec.copy(value))
            return ExtensionDecodeResult(True, tuple(unknown))
        if wire_type != codec.wire_type:
            return ExtensionDecodeResult(False)
        decoded = codec.read(reader)
        if (
            codec.closed_enum
            and codec.enum_values is not None
            and decoded not in codec.enum_values
        ):
            return ExtensionDecodeResult(True, (reader.raw_bytes(tag_start),))
        if extension.repeated:
            self._repeated(extension).append(decoded)
        elif extension in self._values and codec.merge is not None:
            merged = codec.merge(self._values[extension], codec.copy(decoded))
            self._detach_singular(extension)
            self._values[extension] = self._bind_singular(extension, merged)
            self._mark_present(extension)
        else:
            self._detach_singular(extension)
            self._values[extension] = self._bind_singular(
                extension, codec.copy(decoded)
            )
            self._mark_present(extension)
        return ExtensionDecodeResult(True)

    def write_to(self, writer: BinaryWriter, *, deterministic: bool = False) -> None:
        for extension in sorted(self._values, key=lambda item: item.number):
            codec = extension.value_codec
            value = self._values[extension]
            if extension.repeated:
                values = cast(RepeatedValues[Any], value)
                if not values:
                    continue
                if extension.packed and codec.packable:
                    writer.write_tag(extension.number, WIRE_LENGTH_DELIMITED)
                    writer.write_packed(values, codec.write)
                else:
                    for item in values:
                        writer.write_tag(extension.number, codec.wire_type)
                        codec.write_value(writer, item, deterministic=deterministic)
            else:
                if extension not in self._present:
                    continue
                writer.write_tag(extension.number, codec.wire_type)
                codec.write_value(writer, value, deterministic=deterministic)

    def copy_from(self, other: ExtensionValues) -> None:
        if self._registry is not other._registry or self._extendee != other._extendee:
            raise ValueError("extension values belong to another message type")
        if self is other:
            return
        self.clear_all()
        self.merge_from(other)

    def merge_from(self, other: ExtensionValues) -> None:
        if self._registry is not other._registry or self._extendee != other._extendee:
            raise ValueError("extension values belong to another message type")
        for extension, value in other._values.items():
            codec = extension.value_codec
            if extension.repeated:
                destination = self._repeated(extension)
                source = tuple(cast(RepeatedValues[Any], value))
                destination.extend(source)
            elif extension not in other._present:
                continue
            elif extension in self._values and codec.merge is not None:
                merged = codec.merge(self._values[extension], codec.copy(value))
                self._detach_singular(extension)
                self._values[extension] = self._bind_singular(extension, merged)
                self._mark_present(extension)
            else:
                self._detach_singular(extension)
                self._values[extension] = self._bind_singular(
                    extension, codec.copy(value)
                )
                self._mark_present(extension)
