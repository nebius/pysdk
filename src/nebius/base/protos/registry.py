"""Namespace-local direct protobuf symbol and Any resolution."""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import IntEnum
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from .reflection import (
    EnumDescriptor,
    FieldDescriptor,
    FileDescriptor,
    MessageDescriptor,
    Reflection,
    ServiceDescriptor,
)

if TYPE_CHECKING:
    from .direct import Message

_PROTO_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")


@dataclass(frozen=True)
class MessageReference:
    """Lazy reference to one generated direct message class."""

    module: str | None = None
    qualname: str | None = None
    factory: Callable[[], type[Message]] | None = None

    def resolve(self) -> type[Message]:
        if self.factory is not None:
            return self.factory()
        if self.module is None or self.qualname is None:
            raise ValueError("message reference requires a factory or module/qualname")
        value: Any = importlib.import_module(self.module)
        for component in self.qualname.split("."):
            value = getattr(value, component)
        return cast("type[Message]", value)


@dataclass(frozen=True)
class RegistryFragment:
    """Package-owned input used to assemble one namespace registry."""

    symbols: Mapping[str, MessageReference]
    enum_symbols: Mapping[str, MessageReference]
    serialized_files: tuple[bytes, ...]


class Registry:
    """Immutable namespace owner for generated direct message symbols."""

    def __init__(
        self,
        symbols: Mapping[str, MessageReference],
        *,
        any_type: MessageReference | None = None,
        enum_symbols: Mapping[str, MessageReference] = MappingProxyType({}),
        serialized_files: tuple[bytes, ...] = (),
    ) -> None:
        normalized: dict[str, MessageReference] = {}
        for name, reference in symbols.items():
            canonical = name.lstrip(".")
            if not _PROTO_NAME.fullmatch(canonical):
                raise ValueError(f"invalid protobuf message name {name!r}")
            if canonical in normalized:
                raise ValueError(f"duplicate protobuf message name {canonical!r}")
            normalized[canonical] = reference
        self._symbols = MappingProxyType(normalized)
        normalized_enums: dict[str, MessageReference] = {}
        for name, reference in enum_symbols.items():
            canonical = name.lstrip(".")
            if not _PROTO_NAME.fullmatch(canonical):
                raise ValueError(f"invalid protobuf enum name {name!r}")
            if canonical in normalized_enums:
                raise ValueError(f"duplicate protobuf enum name {canonical!r}")
            normalized_enums[canonical] = reference
        self._enum_symbols = MappingProxyType(normalized_enums)
        self._any_type = any_type
        self._cache: dict[str, type[Message]] = {}
        self._enum_cache: dict[str, type[IntEnum]] = {}
        self._lock = RLock()
        self.reflection = (
            Reflection(serialized_files, self._decode_options)
            if serialized_files
            else None
        )

    @classmethod
    def from_fragments(cls, fragments: Iterable[RegistryFragment]) -> Registry:
        """Merge package fragments into one immutable namespace registry."""
        symbols: dict[str, MessageReference] = {}
        enum_symbols: dict[str, MessageReference] = {}
        serialized_files: list[bytes] = []
        for fragment in fragments:
            for name, reference in fragment.symbols.items():
                if name in symbols:
                    raise ValueError(f"duplicate protobuf message name {name!r}")
                symbols[name] = reference
            for name, reference in fragment.enum_symbols.items():
                if name in enum_symbols:
                    raise ValueError(f"duplicate protobuf enum name {name!r}")
                enum_symbols[name] = reference
            serialized_files.extend(fragment.serialized_files)
        return cls(
            symbols,
            any_type=symbols.get("google.protobuf.Any"),
            enum_symbols=enum_symbols,
            serialized_files=tuple(serialized_files),
        )

    @property
    def symbols(self) -> Mapping[str, MessageReference]:
        """Return the immutable lazy symbol mapping."""
        return self._symbols

    def message_class(self, full_name: str) -> type[Message]:
        """Resolve a message class only inside this registry."""
        canonical = full_name.lstrip(".")
        with self._lock:
            cached = self._cache.get(canonical)
            if cached is not None:
                return cached
            try:
                reference = self._symbols[canonical]
            except KeyError as error:
                raise LookupError(
                    f"message {canonical!r} is not registered in this namespace"
                ) from error
            message_type = reference.resolve()
            from .direct import Message

            if not isinstance(message_type, type) or not issubclass(
                message_type, Message
            ):
                raise TypeError(f"symbol {canonical!r} is not a direct Message class")
            if message_type.__PROTO_FULL_NAME__ != canonical:
                raise ValueError(
                    f"symbol {canonical!r} resolved to "
                    f"{message_type.__PROTO_FULL_NAME__!r}"
                )
            if message_type.__REGISTRY__ is not self:
                raise ValueError(f"symbol {canonical!r} belongs to another registry")
            self._cache[canonical] = message_type
            return message_type

    def enum_class(self, full_name: str) -> type[IntEnum]:
        """Resolve a generated enum class only inside this registry."""
        canonical = full_name.lstrip(".")
        with self._lock:
            cached = self._enum_cache.get(canonical)
            if cached is not None:
                return cached
            try:
                reference = self._enum_symbols[canonical]
            except KeyError as error:
                raise LookupError(
                    f"enum {canonical!r} is not registered in this namespace"
                ) from error
            enum_type = reference.resolve()
            if not isinstance(enum_type, type) or not issubclass(enum_type, IntEnum):
                raise TypeError(f"symbol {canonical!r} is not an IntEnum class")
            if getattr(enum_type, "__PROTO_FULL_NAME__", None) != canonical:
                raise ValueError(f"symbol {canonical!r} resolved to the wrong enum")
            if getattr(enum_type, "__REGISTRY__", None) is not self:
                raise ValueError(f"enum {canonical!r} belongs to another registry")
            self._enum_cache[canonical] = enum_type
            return enum_type

    @staticmethod
    def type_name(type_url: str) -> str:
        """Validate a type URL and return its final protobuf-name component."""
        if not isinstance(type_url, str):
            raise TypeError("type URL must be a string")
        prefix, separator, full_name = type_url.rpartition("/")
        if not separator or not prefix or not _PROTO_NAME.fullmatch(full_name):
            raise ValueError(f"malformed Any type URL {type_url!r}")
        return full_name

    def _any_class(self) -> type[Message]:
        if self._any_type is None:
            raise LookupError("google.protobuf.Any is not generated in this namespace")
        message_type = self._any_type.resolve()
        if message_type.__PROTO_FULL_NAME__ != "google.protobuf.Any":
            raise ValueError("configured Any reference is not google.protobuf.Any")
        if message_type.__REGISTRY__ is not self:
            raise ValueError("configured Any class belongs to another registry")
        return message_type

    def _decode_options(self, full_name: str, payload: bytes) -> Message:
        return self.message_class(full_name)._from_string(payload)

    def _require_reflection(self) -> Reflection:
        if self.reflection is None:
            raise LookupError("this registry has no descriptor metadata")
        return self.reflection

    def file_descriptor(self, name: str) -> FileDescriptor:
        return self._require_reflection().files_by_name[name]

    def message_descriptor(self, full_name: str) -> MessageDescriptor:
        return self._require_reflection().messages_by_name[full_name.lstrip(".")]

    def enum_descriptor(self, full_name: str) -> EnumDescriptor:
        return self._require_reflection().enums_by_name[full_name.lstrip(".")]

    def service_descriptor(self, full_name: str) -> ServiceDescriptor:
        return self._require_reflection().services_by_name[full_name.lstrip(".")]

    def extension_descriptor(self, full_name: str) -> FieldDescriptor:
        return self._require_reflection().extensions_by_name[full_name.lstrip(".")]

    def pack_any(
        self,
        message: Message,
        *,
        type_url_prefix: str = "type.googleapis.com",
    ) -> Message:
        """Pack a namespace-owned direct message into its localized Any class."""
        if message.__class__.__REGISTRY__ is not self:
            raise ValueError("cannot pack a message from another registry")
        prefix = type_url_prefix.rstrip("/")
        if not prefix:
            raise ValueError("Any type URL prefix must not be empty")
        full_name = message.__PROTO_FULL_NAME__
        if not _PROTO_NAME.fullmatch(full_name):
            raise ValueError(f"invalid protobuf message name {full_name!r}")
        return self._any_class()(
            type_url=f"{prefix}/{full_name}",
            value=message.SerializeToString(deterministic=True),
        )

    def unpack_any(
        self,
        any_message: Message,
        *,
        expected_type: type[Message] | None = None,
    ) -> Message:
        """Unpack a localized Any through this registry only."""
        if any_message.__class__ is not self._any_class():
            raise ValueError("Any message belongs to another registry")
        fields = any_message.__class__._fields_by_proto_name()
        type_url = cast(str, any_message._get_field(fields["type_url"]))
        payload = cast(bytes, any_message._get_field(fields["value"]))
        full_name = self.type_name(type_url)
        message_type = self.message_class(full_name)
        if expected_type is not None:
            if expected_type.__REGISTRY__ is not self:
                raise ValueError("expected Any type belongs to another registry")
            if message_type is not expected_type:
                raise ValueError(
                    f"Any contains {full_name!r}, expected "
                    f"{expected_type.__PROTO_FULL_NAME__!r}"
                )
        return message_type._from_string(payload)
