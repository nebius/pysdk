"""Provider-free state and binary behavior for generated protobuf messages."""

# Protobuf's compatibility methods intentionally use their established names.
# ruff: noqa: N802

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, MutableMapping, MutableSequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, Protocol, TypeVar, cast

from google.protobuf.message import DecodeError, EncodeError

from nebius.base.error import SDKError
from nebius.base.fieldmask import FieldKey, Mask
from nebius.base.token_sanitizer import TokenSanitizer

from .codec import ValueCodec
from .containers import MapValues
from .extensions import Extension, ExtensionRegistry, ExtensionValues, RepeatedValues
from .wire import WIRE_LENGTH_DELIMITED, BinaryReader, BinaryWriter

if TYPE_CHECKING:
    from .registry import Registry

M = TypeVar("M", bound="Message")
V = TypeVar("V")

_MISSING = object()
_MESSAGE_HARD_MAX_DEPTH = 100
_RESET_MASK_MAX_DEPTH = 1000
_MESSAGE_DECODE_DEPTH: ContextVar[tuple[int, int] | None] = ContextVar(
    "nebius_message_decode_depth", default=None
)
_MESSAGE_ENCODE_DEPTH: ContextVar[tuple[int, int] | None] = ContextVar(
    "nebius_message_encode_depth", default=None
)
_MESSAGE_INITIALIZATION_DEPTH: ContextVar[tuple[int, int, frozenset[int]] | None] = (
    ContextVar("nebius_message_initialization_depth", default=None)
)

_CREDENTIALS_SANITIZER = TokenSanitizer.credentials_sanitizer()


class SerializableMessage(Protocol):
    """Structural input accepted by direct-message copy constructors."""

    def SerializeToString(self, *, deterministic: bool = False) -> bytes: ...


class OneOf:
    """Base for generated, typed views of a selected oneof member."""

    field: str
    name: str

    def __init__(self, message: Message) -> None:
        self._message = message


class OneOfMatchError(SDKError):
    """Raised if a decoded oneof selection has no generated wrapper."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Unexpected oneof field name {name} returned.")


class _ExtensionMapping(MutableMapping[Extension[Any], Any]):
    """Protobuf-compatible ``message.Extensions[extension]`` view."""

    def __init__(self, message: Message) -> None:
        self._message = message

    def __getitem__(self, extension: Extension[Any]) -> Any:
        return self._message.get_extension(extension)

    def __setitem__(self, extension: Extension[Any], value: Any) -> None:
        self._message.set_extension(extension, value)

    def __delitem__(self, extension: Extension[Any]) -> None:
        self._message.clear_extension(extension)

    def __iter__(self) -> Iterator[Extension[Any]]:
        values = self._message._extensions
        if values is None:
            return iter(())
        return (extension for extension, _ in values.present_items())

    def __len__(self) -> int:
        values = self._message._extensions
        return 0 if values is None else sum(1 for _ in values.present_items())

    def __contains__(self, extension: object) -> bool:
        return isinstance(extension, Extension) and self._message.has_extension(
            extension
        )


class _ConvertedSequence(MutableSequence[Any]):
    def __init__(
        self,
        values: RepeatedValues[Any],
        to_python: Callable[[Any], Any],
        from_python: Callable[[object], Any],
    ) -> None:
        self._values = values
        self._to_python = to_python
        self._from_python = from_python

    def __getitem__(self, index: int | slice) -> Any:
        value = self._values[index]
        if isinstance(index, slice):
            return [self._to_python(item) for item in value]
        return self._to_python(value)

    def __setitem__(self, index: int | slice, value: Any) -> None:
        if isinstance(index, slice):
            self._values[index] = [self._from_python(item) for item in value]
        else:
            self._values[index] = self._from_python(value)

    def __delitem__(self, index: int | slice) -> None:
        del self._values[index]

    def __len__(self) -> int:
        return len(self._values)

    def insert(self, index: int, value: Any) -> None:
        self._values.insert(index, self._from_python(value))

    def reverse(self) -> None:
        self._values.reverse()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Iterable):
            return False
        return list(self) == list(other)

    def __repr__(self) -> str:
        return repr(list(self))


class _ConvertedMap(MutableMapping[Any, Any]):
    def __init__(
        self,
        values: MapValues[Any, Any],
        to_python: Callable[[Any], Any],
        from_python: Callable[[object], Any],
    ) -> None:
        self._values = values
        self._to_python = to_python
        self._from_python = from_python

    def __getitem__(self, key: Any) -> Any:
        return self._to_python(self._values[key])

    def __setitem__(self, key: Any, value: Any) -> None:
        self._values[key] = self._from_python(value)

    def __delitem__(self, key: Any) -> None:
        del self._values[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, key: object) -> bool:
        return key in self._values

    def get(self, key: Any, default: Any = None) -> Any:
        value = self._values.get(key, _MISSING)
        return default if value is _MISSING else self._to_python(value)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        value = self._values.get(key, _MISSING)
        if value is not _MISSING:
            return self._to_python(value)
        self[key] = default
        return self[key]

    def pop(self, key: Any, default: Any = _MISSING) -> Any:
        value = self._values.get(key, _MISSING)
        if value is _MISSING:
            if default is _MISSING:
                raise KeyError(key)
            return default
        converted = self._to_python(value)
        del self._values[key]
        return converted

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return False
        return dict(self.items()) == dict(other.items())

    def __repr__(self) -> str:
        return repr(dict(self.items()))


@dataclass(frozen=True, eq=False)
class Field:
    """Generated declaration of one ordinary protobuf field."""

    proto_name: str
    python_name: str
    number: int
    codec: ValueCodec[Any]
    repeated: bool = False
    packed: bool = False
    explicit_presence: bool = False
    required: bool = False
    oneof: str | None = None
    json_name: str | None = None
    default_factory: Callable[[], Any] | None = None
    map_key_codec: ValueCodec[Any] | None = None
    sensitive: bool = False
    credentials: bool = False
    to_python: Callable[[Any], Any] | None = None
    from_python: Callable[[object], Any] | None = None
    public: bool = True

    def default(self) -> Any:
        if self.default_factory is not None:
            return self.default_factory()
        return self.codec.default()

    @property
    def message(self) -> bool:
        return self.codec.bind_mutation is not None

    @property
    def map(self) -> bool:
        return self.map_key_codec is not None

    @property
    def has_presence(self) -> bool:
        return (
            self.explicit_presence
            or self.required
            or (self.message and not self.map)
            or self.oneof is not None
        )


class Message:
    """Base class for generated messages that own their Python state."""

    __MAX_NESTING_DEPTH__: ClassVar[int] = 100
    __FIELDS__: ClassVar[tuple[Field, ...]] = ()
    __PROTO_FULL_NAME__: ClassVar[str]
    __EXTENSION_REGISTRY__: ClassVar[ExtensionRegistry | None] = None
    __REGISTRY__: ClassVar[Registry | None] = None
    __PROTO_DESCRIPTOR__: ClassVar[Any] = None
    __PB2_DESCRIPTOR__: ClassVar[Any] = None
    __PY_TO_PB2__: ClassVar[dict[str, str]] = {}

    def _nesting_limit(self) -> int:
        return min(self.__MAX_NESTING_DEPTH__, _MESSAGE_HARD_MAX_DEPTH)

    def __init__(self, initial_message: object | None = None, **values: object) -> None:
        self._values: dict[Field, Any] = {}
        self._present: set[Field] = set()
        self._oneofs: dict[str, Field] = {}
        self._unknown_fields: list[bytes] = []
        self._views: dict[Field, Any] = {}
        self._reset_mask = Mask()
        self._on_mutation: Callable[[], None] | None = None
        self._mutation_suspended = 0
        self._reset_mask_suspended = 0
        registry = self.__class__.__EXTENSION_REGISTRY__
        self._extensions = (
            ExtensionValues(registry, self.__class__.__PROTO_FULL_NAME__, self._notify)
            if registry is not None
            else None
        )
        if initial_message is not None:
            if isinstance(initial_message, self.__class__):
                self.CopyFrom(initial_message)
            else:
                serializer = getattr(initial_message, "SerializeToString", None)
                if not callable(serializer):
                    raise TypeError(
                        f"expected {self.__class__.__name__} or a serializable message"
                    )
                self.ParseFromString(serializer(deterministic=True))
        with self._suspend_reset_mask():
            fields = self.__class__._public_fields_by_python_name()
            for name, value in values.items():
                try:
                    field = fields[name]
                except KeyError as error:
                    raise TypeError(
                        f"{self.__class__.__name__} got an unexpected field {name!r}"
                    ) from error
                self._set_field(field, value)

    @classmethod
    def _fields_by_number(cls) -> dict[int, Field]:
        return {field.number: field for field in cls.__FIELDS__}

    @classmethod
    def get_descriptor(cls) -> Any:
        """Return this class's registry-owned descriptor facade."""
        descriptor = cls.__PROTO_DESCRIPTOR__ or cls.__PB2_DESCRIPTOR__
        if descriptor is not None:
            return descriptor() if callable(descriptor) else descriptor
        if cls.__REGISTRY__ is None:
            raise ValueError(f"descriptor not configured for {cls.__name__}")
        return cls.__REGISTRY__.message_descriptor(cls.__PROTO_FULL_NAME__)

    @classmethod
    def _fields_by_proto_name(cls) -> dict[str, Field]:
        return {field.proto_name: field for field in cls.__FIELDS__}

    @classmethod
    def _fields_by_python_name(cls) -> dict[str, Field]:
        return {field.python_name: field for field in cls.__FIELDS__}

    @classmethod
    def _public_fields_by_proto_name(cls) -> dict[str, Field]:
        return {field.proto_name: field for field in cls.__FIELDS__ if field.public}

    @classmethod
    def _public_fields_by_python_name(cls) -> dict[str, Field]:
        return {field.python_name: field for field in cls.__FIELDS__ if field.public}

    def _bind_mutation(self, callback: Callable[[], None]) -> None:
        self._on_mutation = callback

    def _notify(self) -> None:
        if self._mutation_suspended == 0 and self._on_mutation is not None:
            self._on_mutation()

    @contextmanager
    def _suspend_mutation(self) -> Iterator[None]:
        self._mutation_suspended += 1
        try:
            yield
        finally:
            self._mutation_suspended -= 1

    @contextmanager
    def _suspend_reset_mask(self) -> Iterator[None]:
        self._reset_mask_suspended += 1
        try:
            yield
        finally:
            self._reset_mask_suspended -= 1

    def _bind_child(self, field: Field, value: Any) -> Any:
        bind_mutation = field.codec.bind_mutation
        if bind_mutation is not None:
            bind_mutation(value, lambda: self._child_changed(field))
        return value

    def _detach_child(self, field: Field) -> None:
        value = self._values.get(field)
        bind_mutation = field.codec.bind_mutation
        if value is not None and bind_mutation is not None:
            bind_mutation(value, lambda: None)

    def _select(self, field: Field) -> None:
        if field.oneof is not None:
            previous = self._oneofs.get(field.oneof)
            if previous is not None and previous is not field:
                self._clear_state(previous)
            self._oneofs[field.oneof] = field
        if field.has_presence:
            self._present.add(field)

    def _child_changed(self, field: Field) -> None:
        self._select(field)
        self._notify()

    def _repeated(self, field: Field) -> RepeatedValues[Any]:
        value = self._values.get(field)
        if value is None:
            value = RepeatedValues(field.codec, self._notify)
            self._values[field] = value
        return cast(RepeatedValues[Any], value)

    def _map(self, field: Field) -> MapValues[Any, Any]:
        value = self._values.get(field)
        if value is None:
            if field.map_key_codec is None:
                raise TypeError("field is not a map")
            value = MapValues(field.map_key_codec, field.codec, self._notify)
            self._values[field] = value
        return cast(MapValues[Any, Any], value)

    def _get_field(self, field: Field, *, absent_is_none: bool = False) -> Any:
        if absent_is_none and field not in self._present:
            return None
        if field.map:
            map_value = self._map(field)
            return self._converted_view(field, map_value)
        if field.repeated:
            repeated_value = self._repeated(field)
            return self._converted_view(field, repeated_value)
        if field in self._values:
            value = self._values[field]
        elif field.message:
            value = self._bind_child(field, field.default())
            self._values[field] = value
        else:
            return field.default()
        if field.message:
            key = FieldKey(field.proto_name)
            if key not in self._reset_mask.field_parts:
                self._reset_mask.field_parts[key] = Mask()
            value.set_mask(self._reset_mask.field_parts[key])
        return field.to_python(value) if field.to_python is not None else value

    def _converted_view(self, field: Field, value: Any) -> Any:
        if field.to_python is None or field.from_python is None:
            return value
        view = self._views.get(field)
        if view is None:
            view = (
                _ConvertedMap(value, field.to_python, field.from_python)
                if field.map
                else _ConvertedSequence(value, field.to_python, field.from_python)
            )
            self._views[field] = view
        return view

    def _set_field(self, field: Field, value: object) -> None:
        if value is None:
            self._clear_state(field)
            self._record_reset(field)
            self._notify()
            return
        if field.map:
            if not isinstance(value, Mapping):
                raise TypeError("map field requires a mapping")
            converted_map: Mapping[Any, Any] = (
                {key: field.from_python(item) for key, item in value.items()}
                if field.from_python is not None
                else value
            )
            self._map(field).replace(converted_map)
            if not self._values[field]:
                self._record_reset(field)
            return
        if field.repeated:
            if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
                raise TypeError("repeated field requires an iterable")
            converted_values: Iterable[Any] = (
                (field.from_python(item) for item in value)
                if field.from_python is not None
                else value
            )
            self._repeated(field).replace(converted_values)
            if not self._values[field]:
                self._record_reset(field)
            return
        raw = field.from_python(value) if field.from_python is not None else value
        owned = field.codec.copy(field.codec.normalize(raw))
        self._detach_child(field)
        self._select(field)
        self._values[field] = self._bind_child(field, owned)
        if not field.has_presence and owned == field.default():
            self._record_reset(field)
        self._notify()

    def _record_reset(self, field: Field) -> None:
        if self._reset_mask_suspended == 0:
            self._reset_mask.field_parts.setdefault(FieldKey(field.proto_name), Mask())

    def _clear_state(self, field: Field) -> None:
        if field.map:
            value = self._values.get(field)
            if value is not None:
                cast(MapValues[Any, Any], value).clear()
            return
        if field.repeated:
            value = self._values.get(field)
            if value is not None:
                cast(RepeatedValues[Any], value).clear()
            return
        self._detach_child(field)
        self._values.pop(field, None)
        self._present.discard(field)
        if field.oneof is not None and self._oneofs.get(field.oneof) is field:
            self._oneofs.pop(field.oneof, None)

    def get_mask(self) -> Mask:
        return self._reset_mask

    def set_mask(self, mask: Mask) -> None:
        self._reset_mask = mask

    @classmethod
    def is_sensitive(cls, field_name: str) -> bool:
        field = cls._public_fields_by_python_name().get(field_name)
        return field.sensitive if field is not None else False

    @classmethod
    def is_credentials(cls, field_name: str) -> bool:
        field = cls._public_fields_by_python_name().get(field_name)
        return field.credentials if field is not None else False

    def __dir__(self) -> Iterable[str]:
        """List generated fields, oneofs, and nested declarations."""
        names = {field.python_name for field in self.__FIELDS__ if field.public}
        names.update(
            field.oneof for field in self.__FIELDS__ if field.public and field.oneof
        )
        for name, value in vars(self.__class__).items():
            if not name.startswith("_") and isinstance(value, type):
                names.add(name)
        return sorted(names)

    def is_default(self, pythonic_name: str) -> bool:
        """Return whether a generated field currently has its default value."""
        try:
            field = self.__class__._public_fields_by_python_name()[pythonic_name]
        except KeyError as error:
            raise ValueError(f"unknown field {pythonic_name!r}") from error
        return self._field_is_default(field, self._values.get(field))

    def check_presence(self, name: str) -> bool:
        """Check presence using a generated Python field name."""
        try:
            field = self.__class__._public_fields_by_python_name()[name]
        except KeyError as error:
            raise ValueError(f"unknown field {name!r}") from error
        return self.HasField(field.proto_name)

    def which_field_in_oneof(self, name: str) -> str | None:
        """Return the generated Python name selected in a protobuf oneof."""
        selected = self.WhichOneof(name)
        if selected is None:
            return None
        field = self.__class__._fields_by_proto_name()[selected]
        return field.python_name if field.public else None

    @staticmethod
    def _repr_field(name: str, value: Any) -> list[str]:
        rendered = repr(value).splitlines() or [""]
        if len(rendered) == 1:
            return [f"  {name}: {rendered[0]}"]
        return [f"  {name}: |", *(f"    {line}" for line in rendered)]

    def __repr__(self) -> str:
        """Render non-default fields without disclosing annotated secrets."""
        lines = [f"{self.__class__.__name__}:"]
        for field in self.__FIELDS__:
            if not field.public:
                continue
            if self._field_is_default(field, self._values.get(field)):
                continue
            if field.sensitive:
                lines.append(f"  {field.python_name}: **HIDDEN**")
                continue
            else:
                value = self._get_field(
                    field,
                    absent_is_none=field.oneof is not None,
                )
                if field.credentials:
                    raw = value if isinstance(value, str) else repr(value)
                    value = (
                        _CREDENTIALS_SANITIZER.sanitize(raw)
                        if _CREDENTIALS_SANITIZER.is_supported(raw)
                        else "**HIDDEN**"
                    )
            lines.extend(self._repr_field(field.python_name, value))
        return "\n".join(lines)

    def get_full_update_reset_mask(self) -> Mask:
        """Build a reset mask from the message's authoritative protobuf state."""
        result = Mask()
        pending: list[tuple[Message, Mask, int]] = [(self, result, 0)]
        while pending:
            message, reset_mask, depth = pending.pop()
            if depth >= _RESET_MASK_MAX_DEPTH:
                raise ValueError("reset mask recursion too deep")
            for field in message.__FIELDS__:
                key = FieldKey(field.proto_name)
                value = message._values.get(field)
                field_mask = reset_mask.field_parts.get(key)
                if field_mask is None:
                    field_mask = Mask()

                if not message._field_has_value(field, value):
                    reset_mask.field_parts[key] = field_mask
                    continue

                if field.map:
                    if field.message:
                        if field_mask.any is None:
                            field_mask.any = Mask()
                        reset_mask.field_parts[key] = field_mask
                        for item in cast(MapValues[Any, Any], value).values():
                            pending.append(
                                (cast(Message, item), field_mask.any, depth + 1)
                            )
                    continue

                if field.repeated:
                    if field.message:
                        if field_mask.any is None:
                            field_mask.any = Mask()
                        reset_mask.field_parts[key] = field_mask
                        for item in cast(RepeatedValues[Any], value):
                            pending.append(
                                (cast(Message, item), field_mask.any, depth + 1)
                            )
                    continue

                if field.message:
                    reset_mask.field_parts[key] = field_mask
                    pending.append((cast(Message, value), field_mask, depth + 1))
                    continue

                if value == field.default():
                    reset_mask.field_parts[key] = field_mask
        return result

    def _field_has_value(self, field: Field, value: Any) -> bool:
        if field.map or field.repeated:
            return bool(value)
        if field.has_presence:
            return field in self._present
        return not self._field_is_default(field, value)

    def _field_is_default(self, field: Field, value: Any) -> bool:
        if field.map or field.repeated:
            return not value
        if field.has_presence:
            return field not in self._present
        return value is None or value == field.default()

    def HasField(self, name: str) -> bool:
        oneof_name = self.__class__._oneof_python_name(name)
        oneof_fields = [
            field
            for field in self.__FIELDS__
            if oneof_name is not None and field.public and field.oneof == oneof_name
        ]
        if oneof_name is not None and oneof_fields:
            selected = self._oneofs.get(oneof_name)
            return selected is not None and selected.public
        try:
            field = self.__class__._public_fields_by_proto_name()[name]
        except KeyError as error:
            raise ValueError(f"unknown field {name!r}") from error
        if field.repeated or not field.has_presence:
            raise ValueError(f"field {name!r} does not have presence")
        return field in self._present

    def WhichOneof(self, name: str) -> str | None:
        oneof_name = self.__class__._oneof_python_name(name)
        if oneof_name is None:
            raise ValueError(f"unknown oneof {name!r}")
        selected = self._oneofs.get(oneof_name)
        return None if selected is None or not selected.public else selected.proto_name

    @classmethod
    def _oneof_python_name(cls, name: str) -> str | None:
        candidates: set[str] = {
            field.oneof
            for field in cls.__FIELDS__
            if field.public and field.oneof is not None
        }
        if name in candidates:
            return name
        return next(
            (
                candidate
                for candidate in candidates
                if cls.__PY_TO_PB2__.get(candidate, candidate) == name
            ),
            None,
        )

    def ClearField(self, name: str) -> None:
        oneof_name = self.__class__._oneof_python_name(name)
        oneof_fields = [
            field
            for field in self.__FIELDS__
            if oneof_name is not None and field.public and field.oneof == oneof_name
        ]
        if oneof_fields and oneof_name is not None:
            selected = self._oneofs.get(oneof_name)
            if selected is not None and selected.public:
                self._clear_state(selected)
                self._record_reset(selected)
                self._notify()
            return
        try:
            field = self.__class__._public_fields_by_proto_name()[name]
        except KeyError as error:
            raise ValueError(f"unknown field {name!r}") from error
        self._clear_state(field)
        self._record_reset(field)
        self._notify()

    def Clear(self) -> None:
        with self._suspend_mutation():
            for field in tuple(self._values):
                self._clear_state(field)
            self._present.clear()
            self._oneofs.clear()
            self._unknown_fields.clear()
            if self._extensions is not None:
                self._extensions.clear_all()
            self._reset_mask = Mask()
        self._notify()

    def _write_field(
        self,
        writer: BinaryWriter,
        field: Field,
        value: Any,
        *,
        deterministic: bool,
    ) -> None:
        writer.write_tag(field.number, field.codec.wire_type)
        field.codec.write_value(writer, value, deterministic=deterministic)

    def SerializeToString(self, *, deterministic: bool = False) -> bytes:
        state = _MESSAGE_ENCODE_DEPTH.get()
        depth, limit = (0, self._nesting_limit()) if state is None else state
        if depth >= limit:
            raise EncodeError("protobuf message nesting exceeds the configured limit")
        token = _MESSAGE_ENCODE_DEPTH.set((depth + 1, limit))
        try:
            return self._serialize_to_string(deterministic=deterministic)
        finally:
            _MESSAGE_ENCODE_DEPTH.reset(token)

    def _serialize_to_string(self, *, deterministic: bool) -> bytes:
        missing = self.FindInitializationErrors()
        if missing:
            raise EncodeError(
                "Message is missing required fields: " + ", ".join(missing)
            )
        writer = BinaryWriter()
        for field in sorted(self.__FIELDS__, key=lambda item: item.number):
            value = self._values.get(field)
            if field.map:
                if not value:
                    continue
                entries = cast(MapValues[Any, Any], value)
                keys = list(entries)
                if deterministic:
                    keys.sort()
                key_codec = cast(ValueCodec[Any], field.map_key_codec)
                for key in keys:
                    nested = BinaryWriter()
                    nested.write_tag(1, key_codec.wire_type)
                    key_codec.write(nested, key)
                    nested.write_tag(2, field.codec.wire_type)
                    field.codec.write_value(
                        nested, entries[key], deterministic=deterministic
                    )
                    writer.write_tag(field.number, WIRE_LENGTH_DELIMITED)
                    writer.write_bytes(nested.to_bytes())
            elif field.repeated:
                if not value:
                    continue
                values = cast(RepeatedValues[Any], value)
                if field.packed and field.codec.packable:
                    writer.write_tag(field.number, WIRE_LENGTH_DELIMITED)
                    writer.write_packed(values, field.codec.write)
                else:
                    for item in values:
                        self._write_field(
                            writer, field, item, deterministic=deterministic
                        )
            elif field.has_presence:
                if field not in self._present:
                    continue
                self._write_field(writer, field, value, deterministic=deterministic)
            elif value is not None and value != field.default():
                self._write_field(writer, field, value, deterministic=deterministic)
        if self._extensions is not None:
            self._extensions.write_to(writer, deterministic=deterministic)
        for raw in self._unknown_fields:
            writer.write_raw(raw)
        return writer.to_bytes()

    @classmethod
    def FromString(cls: type[M], payload: bytes) -> M:
        message = cls()
        message.ParseFromString(payload)
        return message

    @classmethod
    def _from_string(cls: type[M], payload: bytes) -> M:
        """Deserialize internally without invoking generated user warnings."""
        message = cls.__new__(cls)
        Message.__init__(message)
        message.ParseFromString(payload)
        return message

    def ParseFromString(self, payload: bytes) -> int:
        self.Clear()
        return self.MergeFromString(payload)

    def MergeFromString(self, payload: bytes) -> int:
        state = _MESSAGE_DECODE_DEPTH.get()
        depth, limit = (0, self._nesting_limit()) if state is None else state
        if depth >= limit:
            raise DecodeError("protobuf message nesting exceeds the configured limit")
        token = _MESSAGE_DECODE_DEPTH.set((depth + 1, limit))
        try:
            return self._merge_from_string(payload)
        finally:
            _MESSAGE_DECODE_DEPTH.reset(token)

    def _merge_from_string(self, payload: bytes) -> int:
        reader = BinaryReader(payload)
        fields = self.__class__._fields_by_number()
        with self._suspend_mutation():
            while not reader.eof():
                field_number, wire_type, tag_start = reader.read_tag()
                field = fields.get(field_number)
                if field is not None:
                    if self._try_decode_field(field, reader, wire_type, tag_start):
                        continue
                    self._unknown_fields.append(
                        reader.skip_field(field_number, wire_type, tag_start)
                    )
                    continue
                extension = (
                    self.__class__.__EXTENSION_REGISTRY__.by_number(
                        self.__class__.__PROTO_FULL_NAME__, field_number
                    )
                    if self.__class__.__EXTENSION_REGISTRY__ is not None
                    else None
                )
                if extension is not None and self._extensions is not None:
                    result = self._extensions.try_decode(
                        extension, reader, wire_type, tag_start
                    )
                    if result.consumed:
                        self._unknown_fields.extend(result.unknown_fields)
                        continue
                self._unknown_fields.append(
                    reader.skip_field(field_number, wire_type, tag_start)
                )
        return len(payload)

    def _try_decode_field(
        self,
        field: Field,
        reader: BinaryReader,
        wire_type: int,
        tag_start: int,
    ) -> bool:
        codec = field.codec
        if field.map:
            if wire_type != WIRE_LENGTH_DELIMITED:
                return False
            payload = reader.read_bytes()
            if not self._decode_map_entry(field, payload):
                self._unknown_fields.append(reader.raw_bytes(tag_start))
            return True
        if field.repeated and codec.packable and wire_type == WIRE_LENGTH_DELIMITED:
            decoded = reader.read_packed(lambda: codec.read(reader))
            values = self._repeated(field)
            for value in decoded:
                if self._closed_enum_unknown(field, value, packed=True):
                    continue
                values.append(value)
            return True
        if wire_type != codec.wire_type:
            return False
        decoded = codec.read(reader)
        if self._closed_enum_unknown(
            field, decoded, packed=False, raw=reader.raw_bytes(tag_start)
        ):
            return True
        if field.repeated:
            self._repeated(field).append(decoded)
            return True
        if field.oneof is not None:
            selected = self._oneofs.get(field.oneof)
            if selected is not None and selected is not field:
                self._clear_state(selected)
        if field.message and field in self._values and field in self._present:
            merge = codec.merge
            if merge is None:
                raise DecodeError("message codec does not define merge behavior")
            merged = merge(self._values[field], codec.copy(decoded))
            self._detach_child(field)
            self._values[field] = self._bind_child(field, merged)
        else:
            self._detach_child(field)
            self._values[field] = self._bind_child(field, codec.copy(decoded))
        self._select(field)
        return True

    def _decode_map_entry(self, field: Field, payload: bytes) -> bool:
        key_codec = field.map_key_codec
        if key_codec is None:
            raise DecodeError("map field has no key codec")
        key = key_codec.default()
        value = field.codec.default()
        value_seen = False
        invalid = False
        reader = BinaryReader(payload)
        while not reader.eof():
            number, wire_type, start = reader.read_tag()
            if number == 1:
                if wire_type == key_codec.wire_type:
                    key = key_codec.read(reader)
                else:
                    invalid = True
                    reader.skip_field(number, wire_type, start)
            elif number == 2:
                if wire_type == field.codec.wire_type:
                    decoded = field.codec.read(reader)
                    if (
                        field.codec.closed_enum
                        and field.codec.enum_values is not None
                        and decoded not in field.codec.enum_values
                    ):
                        invalid = True
                    elif field.message and value_seen:
                        merge = field.codec.merge
                        if merge is None:
                            raise DecodeError("message map codec has no merge behavior")
                        value = merge(value, decoded)
                    else:
                        value = decoded
                    value_seen = True
                else:
                    invalid = True
                    reader.skip_field(number, wire_type, start)
            else:
                invalid = True
                reader.skip_field(number, wire_type, start)
        if invalid:
            return False
        self._map(field).set_owned(key, value)
        return True

    def _closed_enum_unknown(
        self,
        field: Field,
        value: Any,
        *,
        packed: bool,
        raw: bytes | None = None,
    ) -> bool:
        codec = field.codec
        if (
            not codec.closed_enum
            or codec.enum_values is None
            or value in codec.enum_values
        ):
            return False
        if packed:
            writer = BinaryWriter()
            writer.write_tag(field.number, codec.wire_type)
            writer.write_varint(value & 0xFFFFFFFF)
            self._unknown_fields.append(writer.to_bytes())
        elif raw is not None:
            self._unknown_fields.append(raw)
        return True

    def CopyFrom(self, other: Message) -> None:
        if other is self:
            return
        self._check_same_type(other)
        self.Clear()
        self.MergeFrom(other)

    def MergeFrom(self, other: Message) -> None:
        self._check_same_type(other)
        with self._suspend_mutation():
            for field in self.__FIELDS__:
                value = other._values.get(field)
                if field.map:
                    if value:
                        destination = self._map(field)
                        for key, item in tuple(
                            cast(MapValues[Any, Any], value).items()
                        ):
                            destination[key] = item
                    continue
                if field.repeated:
                    if value:
                        self._repeated(field).extend(
                            tuple(cast(RepeatedValues[Any], value))
                        )
                    continue
                if field.has_presence and field not in other._present:
                    continue
                if not field.has_presence and (
                    value is None or value == field.default()
                ):
                    continue
                if field.message and field in self._values and field in self._present:
                    merge = field.codec.merge
                    if merge is None:
                        raise TypeError("message codec does not define merge behavior")
                    merged = merge(self._values[field], field.codec.copy(value))
                    self._detach_child(field)
                    self._values[field] = self._bind_child(field, merged)
                    self._select(field)
                else:
                    self._detach_child(field)
                    self._values[field] = self._bind_child(
                        field, field.codec.copy(value)
                    )
                    self._select(field)
            if self._extensions is not None and other._extensions is not None:
                self._extensions.merge_from(other._extensions)
            self._unknown_fields.extend(other._unknown_fields)
        self._notify()

    def _check_same_type(self, other: Message) -> None:
        if other.__class__ is not self.__class__:
            raise TypeError(
                f"expected {self.__class__.__name__}, got {other.__class__.__name__}"
            )

    def ByteSize(self) -> int:
        return len(self.SerializeToString())

    def FindInitializationErrors(self) -> list[str]:
        state = _MESSAGE_INITIALIZATION_DEPTH.get()
        depth, limit, active = (
            (0, self._nesting_limit(), frozenset()) if state is None else state
        )
        identity = id(self)
        if depth >= limit or identity in active:
            raise EncodeError("protobuf message nesting exceeds the configured limit")
        token = _MESSAGE_INITIALIZATION_DEPTH.set(
            (depth + 1, limit, active | {identity})
        )
        try:
            return self._find_initialization_errors()
        finally:
            _MESSAGE_INITIALIZATION_DEPTH.reset(token)

    def _find_initialization_errors(self) -> list[str]:
        errors: list[str] = []
        for field in self.__FIELDS__:
            if field.required and field not in self._present:
                errors.append(field.proto_name)
            value = self._values.get(field)
            if field.message and field in self._present:
                for nested in cast(Message, value).FindInitializationErrors():
                    errors.append(f"{field.proto_name}.{nested}")
            elif field.map and field.message and value:
                for key, item in cast(MapValues[Any, Any], value).items():
                    for nested in item.FindInitializationErrors():
                        errors.append(
                            f"{field.proto_name}{self._format_map_key(key)}.{nested}"
                        )
            elif field.repeated and field.message and value:
                for index, item in enumerate(value):
                    for nested in item.FindInitializationErrors():
                        errors.append(f"{field.proto_name}[{index}].{nested}")
        if self._extensions is not None:
            errors.extend(self._extensions.find_initialization_errors())
        return errors

    @staticmethod
    def _format_map_key(key: Any) -> str:
        if isinstance(key, str):
            escaped = key.replace('"', '\\"')
            return f'["{escaped}"]'
        if isinstance(key, bool):
            return "[true]" if key else "[false]"
        return f"[{key}]"

    def IsInitialized(self) -> bool:
        return not self.FindInitializationErrors()

    def get_extension(self, extension: Extension[V]) -> V:
        if self._extensions is None:
            raise ValueError("message has no extension registry")
        return self._extensions.get(extension)

    @property
    def Extensions(self) -> MutableMapping[Extension[Any], Any]:
        return _ExtensionMapping(self)

    def set_extension(self, extension: Extension[V], value: V) -> None:
        if self._extensions is None:
            raise ValueError("message has no extension registry")
        self._extensions.set(extension, value)

    def has_extension(self, extension: Extension[Any]) -> bool:
        if self._extensions is None:
            raise ValueError("message has no extension registry")
        return self._extensions.has(extension)

    def clear_extension(self, extension: Extension[Any]) -> None:
        if self._extensions is None:
            raise ValueError("message has no extension registry")
        self._extensions.clear(extension)

    def to_json(
        self,
        *,
        preserving_proto_field_name: bool = False,
        always_print_fields_with_no_presence: bool = False,
    ) -> str:
        from .json_format import message_to_json

        return message_to_json(
            self,
            preserving_proto_field_name=preserving_proto_field_name,
            always_print_fields_with_no_presence=always_print_fields_with_no_presence,
        )

    @classmethod
    def from_json(
        cls: type[M],
        payload: str | bytes | bytearray,
        *,
        ignore_unknown_fields: bool = False,
    ) -> M:
        from .json_format import message_from_json

        return message_from_json(
            payload, cls(), ignore_unknown_fields=ignore_unknown_fields
        )


def message_codec(message_type: Callable[[], type[M]]) -> ValueCodec[M]:
    """Create a length-delimited codec for a lazily resolved direct message type."""

    def resolve() -> type[M]:
        return message_type()

    def normalize(value: object) -> M:
        expected = resolve()
        if not isinstance(value, expected):
            raise TypeError(f"message field requires {expected.__name__}")
        return value

    def clone(value: M) -> M:
        copied = resolve()()
        copied.CopyFrom(value)
        return copied

    def merge(destination: M, source: M) -> M:
        destination.MergeFrom(source)
        return destination

    return ValueCodec(
        WIRE_LENGTH_DELIMITED,
        lambda reader: resolve().FromString(reader.read_bytes()),
        lambda writer, value: writer.write_bytes(value.SerializeToString()),
        normalize,
        lambda: resolve()(),
        packable=False,
        clone=clone,
        merge=merge,
        bind_mutation=lambda value, callback: value._bind_mutation(callback),
        deterministic_write=lambda writer, value, deterministic: writer.write_bytes(
            value.SerializeToString(deterministic=deterministic)
        ),
        json_kind="message",
    )
