"""Runtime wrappers for protobuf messages, maps, and repeated fields."""

from __future__ import annotations

from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    MutableSequence,
)
from typing import (
    Any,
    TypeVar,
    cast,
    overload,
)

from google.protobuf.descriptor import Descriptor, FieldDescriptor
from google.protobuf.message import Message as PMessage

from nebius.aio.abc import ClientChannelInterface
from nebius.base.error import SDKError
from nebius.base.fieldmask import FieldKey, Mask
from nebius.base.token_sanitizer import TokenSanitizer

from .pb_enum import Enum

T = TypeVar("T")
"""Type placeholder for generic wrappers"""
R = TypeVar("R")
"""Return type placeholder for generic wrappers"""


def is_repeated_field(field: FieldDescriptor) -> bool:
    """Return whether a field is repeated across supported protobuf releases."""
    repeated = getattr(field, "is_repeated", None)
    if repeated is not None:
        return bool(repeated)
    return cast(int, getattr(field, "label")) == FieldDescriptor.LABEL_REPEATED


def simple_wrapper(
    wrap: Callable[[T], R],
) -> Callable[[str, ClientChannelInterface, T], R]:
    """Make a type wrapper for gRPC calls that ignores the first two arguments.

    :param wrap: Callable applied to the third argument.
    :returns: Wrapper that ignores the first two arguments.
    """

    def wrapper(_: str, __: ClientChannelInterface, obj: T) -> R:
        return wrap(obj)

    return wrapper


def wrap_type(obj: T, wrap: Callable[[T], R] | None = None) -> R | T:
    """Wrap a value into an SDK message wrapper, if a wrapper is provided.

    :param obj: Value to wrap.
    :param wrap: Optional wrapper function.
    :returns: Wrapped value or the original object.
    """
    # if isinstance(wrap, type(Enum)):
    #     return wrap.__new__(wrap, obj)
    if wrap is not None:
        return wrap(obj)
    return obj


def unwrap_type(obj: Any, unwrap: Callable[[Any], Any] | None = None) -> Any:
    """Unwrap SDK message wrappers into protobuf-native values.

    :param obj: Value to unwrap.
    :param unwrap: Optional unwrapping function for leaf values.
    :returns: Unwrapped value suitable for protobuf assignment.
    """
    if isinstance(obj, Message):
        return obj.to_proto()
    if isinstance(obj, Mapping):
        return {k: unwrap_type(v, unwrap) for k, v in obj.items()}  # type: ignore[unused-ignore]
    if (
        isinstance(obj, Iterable)
        and not isinstance(obj, str)
        and not isinstance(obj, bytes)
    ):
        return [unwrap_type(x, unwrap) for x in obj]  # type: ignore[unused-ignore]
    if unwrap is not None:
        return unwrap(obj)
    return obj


class OneOf:
    """Marker base for oneof wrappers."""

    name: str


class OneOfMatchError(SDKError):
    """Raised when a oneof field name is unexpected."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Unexpected oneof field name {name} returned.")


def repr_field(key: str, attr: Any, indent: str = "") -> str:
    """Render a field value in a human-readable, multi-line form.

    :param key: Field name.
    :param attr: Field value.
    :param indent: Indentation prefix.
    :returns: Formatted string for inclusion in ``__repr__`` output.
    """
    ret = ""
    el_repr = repr(attr).split("\n")
    if isinstance(attr, Message):
        ret += indent + key + " " + el_repr[0] + "\n"
        for line in el_repr[1:]:
            ret += indent + line + "\n"
    else:
        if len(el_repr) == 1:
            ret += indent + key + ": " + el_repr[0] + "\n"
        else:
            ret += indent + key + ": |\n"
            for line in el_repr:
                ret += indent + "  " + line + "\n"
    return ret


credentials_sanitizer = TokenSanitizer.credentials_sanitizer()
"""Credentials TokenSanitizer singleton instance for sanitizing credential fields."""


def has_method(obj: Any, method: str) -> bool:
    """Return True if ``obj`` exposes a callable attribute named ``method``.

    :param obj: Object to inspect.
    :param method: Method name to check.
    :returns: ``True`` if the method exists and is callable.
    """
    return hasattr(obj, method) and callable(getattr(obj, method))


MaskFunction = Callable[[Any], Mask]
"""Function type that builds a reset mask for a field value."""


class Message:
    """Base class for generated messages that own their Python field state.

    Protobuf objects are created only while encoding or decoding.  Keeping the
    public representation independent from generated ``*_pb2`` modules allows
    two API revisions to coexist in one interpreter without sharing protobuf's
    process-global descriptor pool.
    """

    __PROTO_CLASS__: type[PMessage]
    __PROTO_DESCRIPTOR__: Descriptor
    __PY_TO_PB2__: dict[str, str]
    __default: "Message|None" = None
    __sensitive_fields__: set[str] = set()
    __credentials_fields__: set[str] = set()
    __mask_functions__: dict[str, MaskFunction]

    def __init__(self, initial_message: PMessage | bytes | "Message" | None):
        """Create a direct message, optionally decoding compatible wire data."""
        self.__recorded_reset_mask = Mask()
        self.__values: dict[str, Any] = {}
        self.__present_fields: set[str] = set()
        self.__source_bytes: bytes | None = None
        self.__present = initial_message is not None
        if not hasattr(self, "__PROTO_CLASS__"):
            raise AttributeError(
                f"Proto Class not set for message {self.__class__.__name__}"
            )
        if initial_message is None:
            return
        if isinstance(initial_message, Message):
            self._ensure_message_type(self.get_descriptor().full_name, initial_message)
            wire = initial_message.SerializeToString()
        elif isinstance(initial_message, bytes):
            wire = initial_message
        elif isinstance(initial_message, PMessage):
            expected = self.get_descriptor().full_name
            if initial_message.DESCRIPTOR.full_name != expected:
                raise TypeError(
                    f"Wrong initial message type: expected {expected}, received "
                    f"{initial_message.DESCRIPTOR.full_name}."
                )
            wire = initial_message.SerializeToString()
        else:
            raise TypeError(
                f"Unsupported initial message type {type(initial_message)!r}."
            )
        self._load_wire(wire)

    @staticmethod
    def _message_full_name(value: Any) -> str | None:
        if isinstance(value, Message):
            return value.get_descriptor().full_name
        if isinstance(value, PMessage):
            return value.DESCRIPTOR.full_name
        return None

    @classmethod
    def _ensure_message_type(cls, expected: str, value: Any) -> None:
        actual = cls._message_full_name(value)
        if actual is not None and actual != expected.lstrip("."):
            raise TypeError(
                f"Wrong message type: expected {expected}, received {actual}"
            )

    @staticmethod
    def _copy_proto(value: PMessage) -> PMessage:
        return value.__class__.FromString(value.SerializeToString())

    def _load_wire(self, wire: bytes) -> None:
        proto = self.__PROTO_CLASS__.FromString(wire)
        self.__values.clear()
        self.__present_fields.clear()
        for field, value in proto.ListFields():
            self.__present_fields.add(field.name)
            if is_repeated_field(field):
                if (
                    field.message_type is not None
                    and field.message_type.GetOptions().map_entry
                ):
                    copied: dict[Any, Any] = {}
                    for key, item in value.items():
                        copied[key] = (
                            self._copy_proto(item)
                            if isinstance(item, PMessage)
                            else item
                        )
                    self.__values[field.name] = copied
                else:
                    self.__values[field.name] = [
                        self._copy_proto(item) if isinstance(item, PMessage) else item
                        for item in value
                    ]
            elif isinstance(value, PMessage):
                self.__values[field.name] = self._copy_proto(value)
            else:
                self.__values[field.name] = value
        self.__source_bytes = wire
        self.__present = True

    def _mark_present(self) -> None:
        self.__present = True

    def _is_present(self) -> bool:
        return self.__present

    @classmethod
    def FromString(cls: type[T], wire: bytes) -> T:
        """Decode wire bytes into a new direct message."""
        return cls(wire)  # type: ignore[call-arg]

    def ParseFromString(self, wire: bytes) -> int:
        """Replace this message with decoded wire data."""
        self._load_wire(wire)
        return len(wire)

    def CopyFrom(self, other: PMessage | "Message") -> None:
        """Replace this message with a compatible message."""
        self._ensure_message_type(self.get_descriptor().full_name, other)
        self._load_wire(other.SerializeToString())

    def MergeFrom(self, other: PMessage | "Message") -> None:
        """Merge compatible wire data using protobuf merge semantics."""
        self._ensure_message_type(self.get_descriptor().full_name, other)
        proto = self.to_proto()
        incoming = self.__PROTO_CLASS__.FromString(other.SerializeToString())
        proto.MergeFrom(incoming)
        self._load_wire(proto.SerializeToString())

    def SerializeToString(self, **kwargs: Any) -> bytes:
        """Encode this message with the namespace-local protobuf class."""
        return self.to_proto().SerializeToString(**kwargs)

    @staticmethod
    def _wire_message(type_name: str, value: Any) -> PMessage:
        value = unwrap_type(value)
        if isinstance(value, PMessage):
            Message._ensure_message_type(type_name, value)
            return value
        if type_name == "google.protobuf.Timestamp":
            from .well_known import to_timestamp

            return to_timestamp(value)
        if type_name == "google.protobuf.Duration":
            from .well_known import to_duration

            return to_duration(value)
        if type_name == "google.rpc.Status":
            from nebius.aio.request_status import request_status_to_rpc_status

            return cast(PMessage, request_status_to_rpc_status(value))
        raise TypeError(f"Message field {type_name} cannot encode {type(value)!r}")

    def to_proto(self) -> PMessage:
        """Build a transient private protobuf object for transport interop."""
        proto = self.__PROTO_CLASS__()
        if self.__source_bytes is not None:
            proto.ParseFromString(self.__source_bytes)
        descriptor = self.get_descriptor()
        for field in descriptor.fields:
            proto.ClearField(field.name)
        for field in descriptor.fields:
            name = field.name
            if name not in self.__values:
                continue
            value = self.__values[name]
            if isinstance(value, Message) and not (
                name in self.__present_fields or value._is_present()
            ):
                continue
            target = getattr(proto, name)
            if is_repeated_field(field):
                if (
                    field.message_type is not None
                    and field.message_type.GetOptions().map_entry
                ):
                    for key, item in value.items():
                        value_field = field.message_type.fields_by_name["value"]
                        if value_field.message_type is not None:
                            item = self._wire_message(
                                value_field.message_type.full_name,
                                item,
                            )
                            target[key].ParseFromString(item.SerializeToString())
                        else:
                            target[key] = unwrap_type(item)
                elif field.message_type is not None:
                    for item in value:
                        item = self._wire_message(field.message_type.full_name, item)
                        target.add().ParseFromString(item.SerializeToString())
                else:
                    target.extend(unwrap_type(item) for item in value)
            elif field.message_type is not None:
                value = self._wire_message(field.message_type.full_name, value)
                target.ParseFromString(value.SerializeToString())
            else:
                setattr(proto, name, unwrap_type(value))
        return proto

    def get_full_update_reset_mask(self) -> Mask:
        """Build a reset mask for a full update of this message.

        :returns: :class:`Mask` covering all non-default fields and nested masks.
        """
        desc = self.__class__.get_descriptor()
        ret = Mask()
        for el_key in dir(self):
            el_pb2_key = self.__class__.__PY_TO_PB2__[el_key]
            m_key = FieldKey(el_pb2_key)
            try:
                _ = desc.fields_by_name[el_pb2_key]
            except KeyError:
                continue
            el = getattr(self, el_key)

            m_mask = Mask()
            if el_key in self.__class__.__mask_functions__:
                m_mask = self.__class__.__mask_functions__[el_key](el)
            elif (
                isinstance(el, Map)
                or isinstance(el, Repeated)
                or isinstance(el, Message)
            ):
                if isinstance(el, Message):
                    m_mask = Message.get_full_update_reset_mask(el)
                else:
                    m_mask = el.get_full_update_reset_mask()

            # empty mask is either already set, or not necessary here
            if not m_mask.is_empty() or Message.is_default(self, el_key):
                ret.field_parts[m_key] = m_mask
        return ret

    def set_mask(self, new_mask: Mask) -> None:
        """Replace the tracked reset mask.

        :param new_mask: New mask to store.
        """
        self.__recorded_reset_mask = new_mask

    def get_mask(self) -> Mask:
        """Return the tracked reset mask."""
        return self.__recorded_reset_mask

    @classmethod
    def is_sensitive(cls, field_name: str) -> bool:
        """Return True if the field is marked as sensitive.

        :param field_name: Pythonic field name.
        :returns: ``True`` if the field is sensitive.
        """
        return field_name in cls.__sensitive_fields__

    @classmethod
    def is_credentials(cls, field_name: str) -> bool:
        """Return True if the field contains credentials.

        :param field_name: Pythonic field name.
        :returns: ``True`` if the field should be sanitized.
        """
        return field_name in cls.__credentials_fields__

    def __repr__(self) -> str:
        """Return a human-readable representation of the message, sanitizing sensitive
        fields."""
        ret = self.__class__.__name__ + ":\n"
        desc = self.__class__.get_descriptor()
        for el in dir(self):
            el_pb2 = self.__class__.__PY_TO_PB2__[el]
            try:
                _ = desc.fields_by_name[el_pb2]
            except KeyError:
                continue
            if not Message.is_default(self, el):
                if self.__class__.is_sensitive(el):
                    ret += "  " + el + ": **HIDDEN**\n"
                    continue
                el_attr = getattr(self, el)
                if self.__class__.is_credentials(el):
                    if not isinstance(el_attr, str):
                        el_attr = repr(el_attr)
                    if credentials_sanitizer.is_supported(el_attr):
                        el_attr = credentials_sanitizer.sanitize(el_attr)
                    else:
                        el_attr = "**HIDDEN**"
                ret += repr_field(el, el_attr, "  ")
        return ret[:-1]

    def is_default(self, pythonic_name: str) -> bool:
        """Return True if a field equals its default value.

        :param pythonic_name: Pythonic field name.
        :returns: ``True`` if the field equals the default instance.
        """
        if self.__class__.__default is None:
            self.__class__.__default = self.__class__(None)
        return getattr(self, pythonic_name) == getattr(  # type: ignore[no-any-return]
            self.__class__.__default, pythonic_name
        )

    @classmethod
    def get_descriptor(cls) -> Descriptor:
        """Return the protobuf descriptor for this message class.

        :returns: Protobuf :class:`Descriptor`.
        :raises ValueError: If the descriptor is not configured.
        """
        if not hasattr(cls, "__PROTO_DESCRIPTOR__") or cls.__PROTO_DESCRIPTOR__ is None:  # type: ignore[unused-ignore]
            raise ValueError(f"Descriptor not set for message {cls.__name__}.")
        if isinstance(cls.__PROTO_DESCRIPTOR__, Descriptor):
            return cls.__PROTO_DESCRIPTOR__
        raise ValueError(f"Descriptor not found for message {cls.__name__}.")

    def check_presence(self, name: str) -> bool:
        """Check explicit presence for a field in the protobuf message.

        :param name: Pythonic field name.
        :returns: ``True`` if the field is present.
        """
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        return el_pb2 in self.__present_fields

    def HasField(self, name: str) -> bool:
        """Provide protobuf-compatible presence checks for compatibility facades."""
        descriptor = self.get_descriptor()
        if name in descriptor.oneofs_by_name:
            return self.which_field_in_oneof(name) is not None
        if name not in descriptor.fields_by_name:
            raise ValueError(f"Unknown field {name!r}")
        return name in self.__present_fields

    def WhichOneof(self, name: str) -> str | None:
        """Provide the protobuf spelling of ``which_field_in_oneof``."""
        return self.which_field_in_oneof(name)

    def ClearField(self, name: str) -> None:
        """Clear a protobuf-named field without recording a reset mask."""
        descriptor = self.get_descriptor()
        if name in descriptor.oneofs_by_name:
            for field in descriptor.oneofs_by_name[name].fields:
                self.__values.pop(field.name, None)
                self.__present_fields.discard(field.name)
            return
        if name not in descriptor.fields_by_name:
            raise ValueError(f"Unknown field {name!r}")
        self.__values.pop(name, None)
        self.__present_fields.discard(name)

    def which_field_in_oneof(self, pb2_name: str) -> str | None:
        """Return the set field name for a given oneof.

        :param pb2_name: Protobuf oneof name.
        :returns: Name of the set field or ``None``.
        """
        oneof = self.get_descriptor().oneofs_by_name[pb2_name]
        for field in oneof.fields:
            if field.name in self.__present_fields:
                return field.name
        return None

    def _clear_field(
        self,
        name: str,
    ) -> None:
        """Clear a field and record it in the reset mask.

        :param name: Pythonic field name.
        """
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        fk = FieldKey(el_pb2)
        if fk not in self.__recorded_reset_mask.field_parts:
            self.__recorded_reset_mask.field_parts[fk] = Mask()
        self.__values.pop(el_pb2, None)
        self.__present_fields.discard(el_pb2)

    def _get_field(
        self,
        name: str,
        explicit_presence: bool = False,
        wrap: Callable[[Any], Any] | None = None,
    ) -> Any:
        """Return a field value with optional wrapping and presence handling.

        :param name: Pythonic field name.
        :param explicit_presence: When true, return ``None`` if unset.
        :param wrap: Optional wrapper for the raw value.
        :returns: Field value or ``None`` when not present.
        """
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        field = self.get_descriptor().fields_by_name[el_pb2]
        if explicit_presence and el_pb2 not in self.__present_fields:
            return None
        cached = el_pb2 in self.__values
        if cached:
            ret = self.__values[el_pb2]
        elif is_repeated_field(field):
            ret = (
                {}
                if field.message_type is not None
                and field.message_type.GetOptions().map_entry
                else []
            )
        elif field.message_type is not None:
            ret = getattr(self.__PROTO_CLASS__(), el_pb2)
        else:
            ret = field.default_value
        if (
            not explicit_presence
            and field.message_type is not None
            and field.message_type.full_name
            in {"google.protobuf.Timestamp", "google.protobuf.Duration"}
            and el_pb2 not in self.__present_fields
        ):
            return None
        if cached and isinstance(ret, (Message, Map, Repeated)):
            wrapped = ret
        else:
            wrapped = wrap_type(ret, wrap)
        ret = wrapped
        if isinstance(ret, (Message, Map, Repeated)):
            if (
                isinstance(ret, Message)
                and not cached
                and el_pb2 not in self.__present_fields
            ):
                ret.__present = False
            self.__values[el_pb2] = ret
        set_mask = getattr(ret, "set_mask", None)
        if callable(set_mask):
            el_key = FieldKey(el_pb2)
            if el_key not in self.__recorded_reset_mask.field_parts:
                self.__recorded_reset_mask.field_parts[el_key] = Mask()
            if isinstance(ret, Message):  # may be overwritten
                Message.set_mask(ret, self.__recorded_reset_mask.field_parts[el_key])
            else:
                set_mask(self.__recorded_reset_mask.field_parts[el_key])
        return ret

    def _set_field(
        self,
        name: str,
        value: Any,
        unwrap: Callable[[Any], Any] | None = None,
        explicit_presence: bool = False,
    ) -> None:
        """Set a field value and update the reset mask.

        :param name: Pythonic field name.
        :param value: Value to assign, ``None`` to clear.
        :param unwrap: Optional unwrapping function for leaf values.
        :param explicit_presence: When true, do not treat defaults as clears.
        """
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        field = self.get_descriptor().fields_by_name[el_pb2]
        if field.message_type is not None:
            if field.message_type.GetOptions().map_entry and isinstance(value, Mapping):
                value_descriptor = field.message_type.fields_by_name["value"]
                if value_descriptor.message_type is not None:
                    for item in value.values():
                        self._ensure_message_type(
                            value_descriptor.message_type.full_name,
                            item,
                        )
            elif is_repeated_field(field) and isinstance(value, Iterable):
                for item in value:
                    self._ensure_message_type(field.message_type.full_name, item)
            else:
                self._ensure_message_type(field.message_type.full_name, value)
        self.__values.pop(el_pb2, None)
        self.__present_fields.discard(el_pb2)
        fk = FieldKey(el_pb2)
        if value is None:
            if fk not in self.__recorded_reset_mask.field_parts:
                self.__recorded_reset_mask.field_parts[fk] = Mask()
            return

        if unwrap is not None:
            value = unwrap(value)

        if field.containing_oneof is not None:
            for sibling in field.containing_oneof.fields:
                self.__values.pop(sibling.name, None)
                self.__present_fields.discard(sibling.name)

        if isinstance(value, Mapping):
            value = dict(value)
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            value = list(value)

        if self.__class__.__default is None:
            self.__class__.__default = self.__class__(None)
        if not explicit_presence and getattr(self.__class__.__default, name) == value:
            if fk not in self.__recorded_reset_mask.field_parts:
                self.__recorded_reset_mask.field_parts[fk] = Mask()

        self.__values[el_pb2] = value
        self.__present_fields.add(el_pb2)
        self._mark_present()


MapKey = TypeVar("MapKey", int, str, bool)
"""Type placeholder for map keys."""
CollectibleInner = TypeVar("CollectibleInner", int, str, float, bytes, bool, PMessage)
"""Type placeholder for values on the ProtoBuf side."""
CollectibleOuter = TypeVar(
    "CollectibleOuter", int, str, float, bytes, bool, Enum, Message, PMessage
)
"""Type placeholder for values on the SDK side."""


class Repeated(MutableSequence[CollectibleOuter]):
    """Wrapper for protobuf repeated fields.

    Provides wrapping/unwrapping logic and reset mask calculation for repeated
    fields containing messages or scalar values.

    :param source: Underlying protobuf sequence.
    :param wrap: Optional wrapper for inner values.
    :param unwrap: Optional unwrapping function for outer values.
    :param mask_function: Optional mask builder for elements.
    """

    @classmethod
    def with_wrap(
        cls,
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
        mask_function: MaskFunction | None = None,
    ) -> Callable[[MutableSequence[CollectibleInner]], "Repeated[CollectibleOuter]"]:
        """Create a factory that wraps protobuf repeated fields.

        :param wrap: Optional wrapper for inner values.
        :param unwrap: Optional unwrapping function for outer values.
        :param mask_function: Optional mask builder for elements.
        :returns: Callable that wraps a repeated field.
        """

        def ret(
            source: MutableSequence[CollectibleInner],
        ) -> "Repeated[CollectibleOuter]":
            return cls(source, wrap=wrap, unwrap=unwrap, mask_function=mask_function)  # type: ignore

        return ret

    def __init__(
        self,
        source: MutableSequence[CollectibleInner],
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
        mask_function: MaskFunction | None = None,
    ):
        """Wrap a protobuf repeated field."""
        self._source: MutableSequence[Any] = list(source)
        self._wrap = wrap  # type: ignore
        self._unwrap = unwrap  # type: ignore
        self._mask_function = mask_function

    def _stored_value(self, value: CollectibleOuter) -> Any:
        if isinstance(value, Message):
            return value
        return unwrap_type(value, self._unwrap)

    def insert(self, index: int, value: CollectibleOuter) -> None:
        """Insert a value into the repeated field.

        :param index: Insert position.
        :param value: Value to insert.
        """
        self._source.insert(index, self._stored_value(value))

    def __repr__(self) -> str:
        """Return a multi-line representation of the sequence."""
        if len(self) == 0:
            return " []"
        ret = ""
        for i in self:
            ret += repr_field("-", i)
        return ret

    def get_mask(self) -> Mask | None:
        """Return the mask for this repeated field if empty.

        :returns: Empty :class:`Mask` or ``None`` when non-empty.
        """
        if len(self) == 0:
            return Mask()
        return None

    def get_full_update_reset_mask(self) -> Mask:
        """Compute the reset mask for a full update of this sequence.

        :returns: :class:`Mask` describing updates required for the field.
        """
        ret = Mask()
        if len(self) > 0:
            if isinstance(self[0], Message) or self._mask_function is not None:
                func = (
                    self._mask_function
                    if self._mask_function is not None
                    else Message.get_full_update_reset_mask
                )
                ret.any = Mask()
                for el in self:
                    ret.any += func(el)  # type: ignore
        else:
            ret.any = Mask()
        return ret

    @overload
    def __getitem__(self, index: int) -> CollectibleOuter: ...

    @overload
    def __getitem__(self, index: slice) -> MutableSequence[CollectibleOuter]: ...

    def __getitem__(
        self, index: int | slice
    ) -> CollectibleOuter | MutableSequence[CollectibleOuter]:
        """Return an item or slice from the sequence.

        :param index: Integer index or slice.
        :returns: Wrapped value or list of wrapped values.
        """
        if isinstance(index, int):
            ret = self._source[index]
            if isinstance(ret, Message):
                return ret  # type: ignore[return-value]
            wrapped = wrap_type(ret, self._wrap)
            if isinstance(wrapped, Message):
                self._source[index] = wrapped
            return cast(CollectibleOuter, wrapped)
        elif isinstance(index, slice):  # type: ignore [unused-ignore]
            return [self[i] for i in range(*index.indices(len(self)))]
        else:
            raise TypeError("Index must be int or slice")

    def __setitem__(
        self,
        index: int | slice,
        value: CollectibleOuter | Iterable[CollectibleOuter],
    ) -> None:
        """Set an item or slice in the sequence.

        :param index: Integer index or slice.
        :param value: Value or iterable of values.
        """
        if isinstance(index, int):
            if len(self._source) == index:
                self._source.append(self._stored_value(value))  # type: ignore[arg-type]
                return
            self._source[index] = self._stored_value(value)  # type: ignore[arg-type]
        elif isinstance(index, slice):  # type: ignore [unused-ignore]
            if not isinstance(value, Iterable):
                raise TypeError("Slice value must be iterable")
            self._source[index] = [
                self._stored_value(item) for item in value  # type: ignore[arg-type]
            ]

    def __delitem__(self, index: int | slice) -> None:
        """Delete an item or slice from the sequence."""
        self._source.__delitem__(index)

    def __len__(self) -> int:
        """Return the number of elements."""
        return len(self._source)


class Map(MutableMapping[MapKey, CollectibleOuter]):
    """Wrapper for protobuf map fields with optional wrapping.

    :param source: Underlying protobuf mapping.
    :param wrap: Optional wrapper for inner values.
    :param unwrap: Optional unwrapping function for outer values.
    :param mask_function: Optional mask builder for values.
    """

    @classmethod
    def with_wrap(
        cls,
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
        mask_function: MaskFunction | None = None,
    ) -> Callable[
        [MutableMapping[MapKey, CollectibleInner]], "Map[MapKey, CollectibleOuter]"
    ]:
        """Create a factory that wraps protobuf map fields.

        :param wrap: Optional wrapper for inner values.
        :param unwrap: Optional unwrapping function for outer values.
        :param mask_function: Optional mask builder for values.
        :returns: Callable that wraps a map field.
        """

        def ret(
            source: MutableMapping[MapKey, CollectibleInner],
        ) -> "Map[MapKey, CollectibleOuter]":
            return cls(source, wrap=wrap, unwrap=unwrap, mask_function=mask_function)  # type: ignore[arg-type]

        return ret

    def get_full_update_reset_mask(self) -> Mask:
        """Compute the reset mask for a full update of this map.

        :returns: :class:`Mask` describing updates required for the field.
        """
        ret = Mask()
        if len(self) > 0:
            for _, el in self.items():
                if not isinstance(el, Message) and self._mask_function is None:
                    return Mask()
                if self._mask_function is None:
                    m_mask = Message.get_full_update_reset_mask(el)  # type: ignore
                else:
                    m_mask = self._mask_function(el)
                if not m_mask.is_empty():
                    if ret.any is None:
                        ret.any = Mask()
                    ret.any += m_mask
        else:
            ret.any = Mask()
        return ret

    def __init__(
        self,
        source: MutableMapping[MapKey, CollectibleInner],
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
        mask_function: MaskFunction | None = None,
    ):
        """Wrap a protobuf map field."""
        self._source: MutableMapping[MapKey, Any] = dict(source)
        self._wrap: Callable[[CollectibleInner], CollectibleOuter] = wrap  # type: ignore[assignment]
        self._unwrap: Callable[[CollectibleOuter], CollectibleInner] = unwrap  # type: ignore[assignment]
        self._mask_function = mask_function

    def _stored_value(self, value: CollectibleOuter) -> Any:
        if isinstance(value, Message):
            return value
        return unwrap_type(value, self._unwrap)

    def __repr__(self) -> str:
        """Return a multi-line representation of the map."""
        if len(self) == 0:
            return " {}"
        ret = ""
        for k, v in self.items():
            ret += repr_field(repr(k), v)
        return ret

    def __getitem__(self, key: MapKey) -> CollectibleOuter:
        """Return a wrapped map value.

        :param key: Map key.
        :returns: Wrapped map value.
        """
        ret = self._source[key]  # type: ignore[assignment,unused-ignore]
        if isinstance(ret, Message):
            return ret  # type: ignore[return-value]
        wrapped = wrap_type(ret, self._wrap)
        if isinstance(wrapped, Message):
            self._source[key] = wrapped
        return cast(CollectibleOuter, wrapped)

    def __setitem__(self, key: MapKey, value: CollectibleOuter) -> None:
        """Set a map entry.

        :param key: Map key.
        :param value: Value to store.
        """
        self._source[key] = self._stored_value(value)

    def __delitem__(self, key: MapKey) -> None:
        """Delete a map entry."""
        self._source.__delitem__(key)  # type: ignore[unused-ignore]

    def __iter__(self) -> Iterator[MapKey]:
        """Return an iterator over map keys."""
        return self._source.__iter__()  # type: ignore[unused-ignore]

    def __len__(self) -> int:
        """Return the number of entries."""
        return len(self._source)  # type: ignore[unused-ignore]
