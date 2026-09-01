"""Descriptor-driven direct protobuf classes for the Go PySDK generator."""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, MutableMapping, MutableSequence
from datetime import datetime, timedelta
from importlib import import_module
from importlib.metadata import distributions
from inspect import Parameter, Signature
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Any, cast

from . import _google_namespace as _google_namespace
from .codec import (
    BOOL,
    BYTES,
    DOUBLE,
    FIXED32,
    FIXED64,
    FLOAT,
    INT32,
    INT64,
    SFIXED32,
    SFIXED64,
    SINT32,
    SINT64,
    STRING,
    UINT32,
    UINT64,
    ValueCodec,
    enum_codec,
)
from .direct import Field, Message, OneOf, OneOfMatchError, SerializableMessage, message_codec
from .extensions import Extension, ExtensionRegistry
from .pb_enum import Enum
from .reflection import FieldDescriptor, Reflection
from .registry import MessageReference, Registry
from .unset import Unset, UnsetType
from .well_known_direct import (
    datetime_to_timestamp,
    duration_to_timedelta,
    request_status_to_status,
    status_to_request_status,
    timedelta_to_duration,
    timestamp_to_datetime,
)

_MESSAGES: dict[str, type[Message]] = {}
_ENUMS: dict[str, type[Enum]] = {}
_EXPORTED_MESSAGES: set[str] = set()
_EXPORTED_ENUMS: set[str] = set()
_CLIENTS: dict[str, type[Any]] = {}
_INITIAL_PARAMETER_NAMES: dict[str, str] = {}
_ANNOTATION_DEPENDENTS: dict[str, set[str]] = {}
_PROTO_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
_PYTHON_PACKAGE_ROOT = __name__.rsplit(".base.protos.dynamic", 1)[0]
_API_PACKAGE_ROOT = _PYTHON_PACKAGE_ROOT + ".api"
_API_LOCAL_ROOT = Path(__file__).resolve().parents[2] / "api"


def _find_distribution_api_modules() -> frozenset[str] | None:
    """Return API modules owned by the distribution containing this runtime.

    Installed namespace packages can share one physical ``nebius/api`` tree.
    Distribution metadata is the only reliable way to distinguish this SDK's
    files from modules contributed by another wheel. Bazel and source-tree
    execution have no owning distribution, so callers fall back to the local
    tree in that case.
    """
    runtime = Path(__file__).resolve()
    package_parts = tuple(_PYTHON_PACKAGE_ROOT.split("."))
    runtime_parts = package_parts + ("base", "protos", "dynamic.py")
    api_parts = package_parts + ("api",)
    for distribution in distributions():
        files = distribution.files
        if files is None:
            continue
        owns_runtime = any(
            tuple(file.parts) == runtime_parts and Path(str(distribution.locate_file(file))).resolve() == runtime
            for file in files
        )
        if not owns_runtime:
            continue
        modules = {
            _API_PACKAGE_ROOT + "." + ".".join(file.parts[len(api_parts) : -1])
            for file in files
            if tuple(file.parts[: len(api_parts)]) == api_parts
            and file.name == "__init__.py"
            and len(file.parts) > len(api_parts) + 1
        }
        return frozenset(modules)
    return None


_DISTRIBUTION_API_MODULES_UNSET = object()
_DISTRIBUTION_API_MODULES: frozenset[str] | None | object = _DISTRIBUTION_API_MODULES_UNSET
_DISTRIBUTION_API_MODULES_LOCK = RLock()


def _distribution_api_modules() -> frozenset[str] | None:
    """Return and cache the API-module boundary for this installation."""
    global _DISTRIBUTION_API_MODULES
    with _DISTRIBUTION_API_MODULES_LOCK:
        if _DISTRIBUTION_API_MODULES is _DISTRIBUTION_API_MODULES_UNSET:
            _DISTRIBUTION_API_MODULES = _find_distribution_api_modules()
        return cast(frozenset[str] | None, _DISTRIBUTION_API_MODULES)


class _DynamicExtensionRegistry(ExtensionRegistry):
    @property
    def frozen(self) -> bool:
        # Descriptor-bearing Bazel packages are imported lazily, so extension
        # declarations arrive incrementally. ExtensionValues only needs stable
        # lookups while decoding one message; registration remains append-only.
        return True

    def by_number(self, extendee: str, number: int) -> Extension[Any] | None:
        registered = super().by_number(extendee, number)
        if registered is not None:
            return registered
        _ensure_all_api_modules()
        return super().by_number(extendee, number)

    def by_name(self, full_name: str) -> Extension[Any] | None:
        registered = super().by_name(full_name)
        if registered is not None:
            return registered
        _ensure_all_api_modules()
        return super().by_name(full_name)


class _LazyExtensionHandles(dict[str, Extension[Any]]):
    def __getitem__(self, key: str) -> Extension[Any]:
        _ensure_all_api_modules()
        return super().__getitem__(key)

    def __contains__(self, key: object) -> bool:
        _ensure_all_api_modules()
        return super().__contains__(key)

    def __iter__(self) -> Iterator[str]:
        _ensure_all_api_modules()
        return super().__iter__()

    def __len__(self) -> int:
        _ensure_all_api_modules()
        return super().__len__()

    def get(self, key: str, default: Any = None) -> Any:
        _ensure_all_api_modules()
        return super().get(key, default)

    def items(self) -> Any:
        _ensure_all_api_modules()
        return super().items()

    def keys(self) -> Any:
        _ensure_all_api_modules()
        return super().keys()

    def values(self) -> Any:
        _ensure_all_api_modules()
        return super().values()

    def copy(self) -> dict[str, Extension[Any]]:
        _ensure_all_api_modules()
        return super().copy()

    def __eq__(self, other: object) -> bool:
        _ensure_all_api_modules()
        return super().__eq__(other)

    def __ne__(self, other: object) -> bool:
        _ensure_all_api_modules()
        return super().__ne__(other)

    def __repr__(self) -> str:
        _ensure_all_api_modules()
        return super().__repr__()

    def __or__(self, other: Any) -> Any:
        _ensure_all_api_modules()
        return super().__or__(other)

    def __ror__(self, other: Any) -> Any:
        _ensure_all_api_modules()
        return super().__ror__(other)


def _ensure_all_api_modules() -> None:
    registry = globals().get("REGISTRY")
    if isinstance(registry, DynamicRegistry):
        registry.load_all()


_EXTENSIONS = _DynamicExtensionRegistry()
_EXTENSION_HANDLES = _LazyExtensionHandles()
_EXTENDEES: set[str] = set()
_EXTENSION_LOCK = RLock()
_CLASS_CACHE_LOCK = RLock()
EXTENSIONS = _EXTENSIONS
EXTENSION_HANDLES = _EXTENSION_HANDLES


class DynamicRegistry(Registry):
    """Registry of SDK-owned message classes and descriptor facades."""

    def __init__(self) -> None:
        self._serialized_files: dict[str, bytes] = {}
        self._reflection: Reflection | None = None
        self._loading_all_modules = False
        self._all_modules_loaded = False
        self._lock = RLock()
        self._load_lock = RLock()

    @staticmethod
    def _import_symbol_owner(full_name: str) -> None:
        owned_modules = _distribution_api_modules()
        components = full_name.lstrip(".").split(".")[:-1]
        while components:
            if not (_API_LOCAL_ROOT.joinpath(*components) / "__init__.py").is_file():
                components.pop()
                continue
            module_name = _API_PACKAGE_ROOT + "." + ".".join(components)
            if owned_modules is not None and module_name not in owned_modules:
                components.pop()
                continue
            try:
                import_module(module_name)
            except ModuleNotFoundError as error:
                if error.name is None or not (error.name == module_name or module_name.startswith(error.name + ".")):
                    raise
                components.pop()
                continue
            return

    def _load_all_api_modules(self) -> None:
        # Do not hold the descriptor-registration lock while importing. A
        # normal import in another thread may hold Python's module lock and
        # call register_file(), producing a lock-order deadlock.
        with self._load_lock:
            with self._lock:
                if self._all_modules_loaded or self._loading_all_modules:
                    return
                self._loading_all_modules = True
            try:
                owned_modules = _distribution_api_modules()
                if owned_modules is not None:
                    module_names = set(owned_modules)
                else:
                    module_names = set()
                    root_path = Path(__file__).resolve().parents[2] / "api"
                    for source in root_path.rglob("__init__.py"):
                        relative = source.parent.relative_to(root_path)
                        if relative.parts:
                            module_names.add(_API_PACKAGE_ROOT + "." + ".".join(relative.parts))
                for module_name in sorted(module_names):
                    import_module(module_name)
                with self._lock:
                    self._all_modules_loaded = True
            finally:
                with self._lock:
                    self._loading_all_modules = False

    def load_all(self) -> None:
        """Import every SDK API module available in this installation."""
        self._load_all_api_modules()

    def _reflection_snapshot(self) -> Reflection:
        with self._lock:
            current = self._reflection
            if current is None:
                current = Reflection(
                    tuple(self._serialized_files.values()),
                    self._decode_options,
                )
                self._reflection = current
                with _CLASS_CACHE_LOCK:
                    for name, message in _MESSAGES.items():
                        message_descriptor = current.messages_by_name.get(name)
                        if message_descriptor is not None:
                            message.__PROTO_DESCRIPTOR__ = message_descriptor
                            message.__PB2_DESCRIPTOR__ = message_descriptor
                    for name, enum in _ENUMS.items():
                        enum_descriptor = current.enums_by_name.get(name)
                        if enum_descriptor is not None:
                            enum.__PROTO_DESCRIPTOR__ = enum_descriptor
                            enum.__PB2_DESCRIPTOR__ = enum_descriptor
            return current

    @property
    def reflection(self) -> Reflection:
        self._load_all_api_modules()
        return self._reflection_snapshot()

    def _decode_options(self, full_name: str, payload: bytes) -> Message:
        return self._internal_message_class(full_name)._from_string(payload)

    @property
    def symbols(self) -> Mapping[str, MessageReference]:
        self._load_all_api_modules()
        with _CLASS_CACHE_LOCK:
            exported_messages = tuple(_EXPORTED_MESSAGES)
        return MappingProxyType(
            {
                name: MessageReference(
                    factory=cast(
                        Callable[[], type[Message]],
                        lambda canonical=name: self.message_class(canonical),
                    ),
                )
                for name in exported_messages
            },
        )

    @staticmethod
    def type_name(type_url: str) -> str:
        if not isinstance(type_url, str):
            raise TypeError("type URL must be a string")
        prefix, separator, full_name = type_url.rpartition("/")
        if not separator or not prefix or not _PROTO_NAME.fullmatch(full_name):
            raise ValueError(f"malformed Any type URL {type_url!r}")
        return full_name

    def message_class(self, full_name: str) -> type[Message]:
        canonical = full_name.lstrip(".")
        with _CLASS_CACHE_LOCK:
            wrapper = _MESSAGES.get(canonical) if canonical in _EXPORTED_MESSAGES else None
        if wrapper is not None:
            return wrapper
        self._import_symbol_owner(canonical)
        with _CLASS_CACHE_LOCK:
            wrapper = _MESSAGES.get(canonical)
            if wrapper is not None and canonical in _EXPORTED_MESSAGES:
                return wrapper
        raise LookupError(f"message {canonical!r} is not registered in this namespace")

    def _internal_message_class(self, full_name: str) -> type[Message]:
        """Resolve descriptor-only option messages without exporting them."""
        canonical = full_name.lstrip(".")
        with _CLASS_CACHE_LOCK:
            wrapper = _MESSAGES.get(canonical)
        if wrapper is not None:
            return wrapper
        descriptor = self._reflection_snapshot().messages_by_name[canonical]
        return message_class(canonical, descriptor.name, _exported=False)

    def enum_class(self, full_name: str) -> type[Enum]:
        canonical = full_name.lstrip(".")
        with _CLASS_CACHE_LOCK:
            wrapper = _ENUMS.get(canonical) if canonical in _EXPORTED_ENUMS else None
        if wrapper is not None:
            return wrapper
        self._import_symbol_owner(canonical)
        with _CLASS_CACHE_LOCK:
            wrapper = _ENUMS.get(canonical)
            if wrapper is not None and canonical in _EXPORTED_ENUMS:
                return wrapper
        raise LookupError(f"enum {canonical!r} is not registered in this namespace")

    def _internal_enum_class(self, full_name: str) -> type[Enum]:
        """Resolve descriptor-only enums without exporting them."""
        canonical = full_name.lstrip(".")
        with _CLASS_CACHE_LOCK:
            wrapper = _ENUMS.get(canonical)
        if wrapper is not None:
            return wrapper
        descriptor = self._reflection_snapshot().enums_by_name[canonical]
        values = {value.name: value.number for value in descriptor.values}
        return enum_class(canonical, descriptor.name, values, _exported=False)

    def file_descriptor(self, name: str) -> Any:
        with self._lock:
            registered = name in self._serialized_files
        if not registered:
            self._load_all_api_modules()
        return self._reflection_snapshot().files_by_name[name]

    def message_descriptor(self, full_name: str) -> Any:
        self._import_symbol_owner(full_name)
        return self._reflection_snapshot().messages_by_name[full_name.lstrip(".")]

    def enum_descriptor(self, full_name: str) -> Any:
        self._import_symbol_owner(full_name)
        return self._reflection_snapshot().enums_by_name[full_name.lstrip(".")]

    def service_descriptor(self, full_name: str) -> Any:
        self._import_symbol_owner(full_name)
        return self._reflection_snapshot().services_by_name[full_name.lstrip(".")]

    def extension_descriptor(self, full_name: str) -> Any:
        self._import_symbol_owner(full_name)
        return self._reflection_snapshot().extensions_by_name[full_name.lstrip(".")]

    def client_class(self, full_name: str) -> type[Any]:
        canonical = full_name.lstrip(".")
        client = _CLIENTS.get(canonical)
        if client is not None:
            return client
        package = canonical.rsplit(".", 1)[0]
        import_module(_API_PACKAGE_ROOT + "." + package)
        try:
            return _CLIENTS[canonical]
        except KeyError as error:
            raise LookupError(f"client {canonical!r} is not registered") from error

    def pack_any(
        self,
        message: Message,
        *,
        type_url_prefix: str = "type.googleapis.com",
    ) -> Message:
        if cast(Any, message.__class__.__REGISTRY__) is not self:
            raise ValueError("cannot pack a message from another registry")
        prefix = type_url_prefix.rstrip("/")
        if not prefix:
            raise ValueError("Any type URL prefix must not be empty")
        packed: Message = self.message_class("google.protobuf.Any")(
            type_url=f"{prefix}/{message.__PROTO_FULL_NAME__}",
            value=message.SerializeToString(deterministic=True),
        )
        return packed

    def unpack_any(
        self,
        any_message: Message,
        *,
        expected_type: type[Message] | None = None,
    ) -> Message:
        if any_message.__class__ is not self.message_class("google.protobuf.Any"):
            raise ValueError("Any message belongs to another registry")
        full_name = self.type_name(cast(Any, any_message).type_url)
        message_type = self.message_class(full_name)
        if expected_type is not None and message_type is not expected_type:
            raise ValueError(f"Any contains {full_name!r}, expected {expected_type.__PROTO_FULL_NAME__!r}")
        return message_type._from_string(cast(Any, any_message).value)


REGISTRY = DynamicRegistry()


def register_file(name: str, serialized: bytes) -> None:
    """Register one serialized file descriptor, rejecting name conflicts."""
    with REGISTRY._lock:
        previous = REGISTRY._serialized_files.get(name)
        if previous is not None:
            if previous != serialized:
                raise ValueError(f"conflicting descriptor registration for {name!r}")
            return
        REGISTRY._serialized_files[name] = serialized
        REGISTRY._reflection = None


def _codec_for(field: FieldDescriptor, *, internal: bool = False) -> ValueCodec[Any]:
    scalar = cast(
        dict[int, ValueCodec[Any]],
        {
            FieldDescriptor.TYPE_DOUBLE: DOUBLE,
            FieldDescriptor.TYPE_FLOAT: FLOAT,
            FieldDescriptor.TYPE_INT64: INT64,
            FieldDescriptor.TYPE_UINT64: UINT64,
            FieldDescriptor.TYPE_INT32: INT32,
            FieldDescriptor.TYPE_FIXED64: FIXED64,
            FieldDescriptor.TYPE_FIXED32: FIXED32,
            FieldDescriptor.TYPE_BOOL: BOOL,
            FieldDescriptor.TYPE_STRING: STRING,
            FieldDescriptor.TYPE_BYTES: BYTES,
            FieldDescriptor.TYPE_UINT32: UINT32,
            FieldDescriptor.TYPE_SFIXED32: SFIXED32,
            FieldDescriptor.TYPE_SFIXED64: SFIXED64,
            FieldDescriptor.TYPE_SINT32: SINT32,
            FieldDescriptor.TYPE_SINT64: SINT64,
        },
    ).get(field.type)
    if scalar is not None:
        return scalar
    if field.enum_type is not None:
        enum_name = field.enum_type.full_name
        names = {value.name: value.number for value in field.enum_type.values}
        default_value = field.default_value
        if not isinstance(default_value, int):
            default_value = field.enum_type.values[0].number
        return enum_codec(
            names.values(),
            default=int(default_value),
            closed=bool(getattr(field.enum_type, "is_closed", False)),
            names=names,
            enum_type=lambda: (
                REGISTRY._internal_enum_class(enum_name) if internal else REGISTRY.enum_class(enum_name)
            ),
        )
    if field.message_type is not None:
        message_name = field.message_type.full_name
        return message_codec(
            lambda: (
                REGISTRY._internal_message_class(message_name) if internal else REGISTRY.message_class(message_name)
            ),
        )
    raise TypeError(f"unsupported protobuf field type {field.type}")


def _well_known_adapters(
    field: FieldDescriptor,
    *,
    internal: bool = False,
) -> tuple[Any | None, Any | None]:
    full_name = getattr(field.message_type, "full_name", "")

    def factory() -> type[Message]:
        if internal:
            return REGISTRY._internal_message_class(full_name)
        return REGISTRY.message_class(full_name)

    if full_name == "google.protobuf.Timestamp":
        return timestamp_to_datetime, lambda value: datetime_to_timestamp(value, factory)
    if full_name == "google.protobuf.Duration":
        return duration_to_timedelta, lambda value: timedelta_to_duration(value, factory)
    if full_name == "google.rpc.Status":
        return status_to_request_status, lambda value: request_status_to_status(value, factory)
    return None, None


def _is_repeated(field: FieldDescriptor) -> bool:
    return field.is_repeated


def _is_required(field: FieldDescriptor) -> bool:
    return field.is_required


def _has_optional_keyword(field: FieldDescriptor) -> bool:
    return field.proto3_optional


def _direct_field(
    descriptor: FieldDescriptor,
    python_name: str,
    python_oneofs: Mapping[str, str] | None = None,
    deprecation_details: str | None = None,
    enum_value_deprecations: Mapping[int, tuple[tuple[str, str], ...]] | None = None,
    *,
    sensitive: bool = False,
    credentials: bool = False,
    immutable: bool = False,
    immutable_oneof: bool = False,
    internal: bool = False,
) -> Field:
    map_key_codec: ValueCodec[Any] | None = None
    codec_descriptor = descriptor
    repeated = _is_repeated(descriptor)
    if descriptor.message_type is not None and descriptor.message_type.is_map_entry:
        key_descriptor = descriptor.message_type.fields_by_name["key"]
        codec_descriptor = descriptor.message_type.fields_by_name["value"]
        map_key_codec = _codec_for(key_descriptor, internal=internal)
        repeated = False
    to_python, from_python = _well_known_adapters(codec_descriptor, internal=internal)
    optional_keyword = _has_optional_keyword(descriptor)
    return Field(
        descriptor.name,
        python_name,
        descriptor.number,
        _codec_for(codec_descriptor, internal=internal),
        repeated=repeated,
        packed=bool(getattr(descriptor, "is_packed", False)),
        # Message fields have protobuf presence, but the direct Python API
        # exposes their mutable default object on access. Scalar presence is
        # tracked separately from whether an absent getter returns ``None``.
        explicit_presence=descriptor.has_presence and descriptor.message_type is None,
        absent_is_none=optional_keyword,
        required=_is_required(descriptor),
        oneof=(
            (python_oneofs or {}).get(
                descriptor.containing_oneof.name,
                descriptor.containing_oneof.name,
            )
            if descriptor.containing_oneof is not None and not optional_keyword
            else None
        ),
        json_name=getattr(descriptor, "json_name", descriptor.name),
        map_key_codec=map_key_codec,
        sensitive=sensitive,
        credentials=credentials,
        immutable=immutable,
        immutable_oneof=immutable_oneof,
        to_python=to_python,
        from_python=from_python,
        deprecation_details=deprecation_details,
        enum_value_deprecations=enum_value_deprecations,
    )


def _runtime_value_annotation(field: FieldDescriptor) -> Any:
    """Return the direct Python value type exposed for one descriptor field."""
    if field.type == FieldDescriptor.TYPE_BOOL:
        return bool
    if field.type == FieldDescriptor.TYPE_STRING:
        return str
    if field.type == FieldDescriptor.TYPE_BYTES:
        return bytes
    if field.type in (FieldDescriptor.TYPE_DOUBLE, FieldDescriptor.TYPE_FLOAT):
        return float
    if field.type == FieldDescriptor.TYPE_ENUM and field.enum_type is not None:
        return _ENUMS.get(field.enum_type.full_name, int)
    if field.type in (
        FieldDescriptor.TYPE_INT32,
        FieldDescriptor.TYPE_SINT32,
        FieldDescriptor.TYPE_UINT32,
        FieldDescriptor.TYPE_INT64,
        FieldDescriptor.TYPE_SINT64,
        FieldDescriptor.TYPE_UINT64,
        FieldDescriptor.TYPE_FIXED32,
        FieldDescriptor.TYPE_SFIXED32,
        FieldDescriptor.TYPE_FIXED64,
        FieldDescriptor.TYPE_SFIXED64,
    ):
        return int
    if field.message_type is not None:
        full_name = field.message_type.full_name
        if full_name == "google.protobuf.Timestamp":
            return datetime
        if full_name == "google.protobuf.Duration":
            return timedelta
        if full_name == "google.rpc.Status":
            from ...aio.request_status import RequestStatus

            return RequestStatus
        return _MESSAGES.get(full_name, object)
    return object


def _constructor_annotation(field: FieldDescriptor) -> Any:
    """Return the runtime constructor annotation matching generated setters."""
    if field.message_type is not None and field.message_type.is_map_entry:
        key = _runtime_value_annotation(field.message_type.fields_by_name["key"])
        value = _runtime_value_annotation(field.message_type.fields_by_name["value"])
        annotation: Any = cast(Any, Mapping)[key, value]
    else:
        value = _runtime_value_annotation(field)
        if field.is_repeated:
            annotation = cast(Any, Iterable)[value]
        else:
            annotation = value
    return annotation | None | UnsetType


def _property_annotations(field: FieldDescriptor) -> tuple[Any, Any]:
    """Return the getter and setter annotations for a generated property."""
    if field.message_type is not None and field.message_type.is_map_entry:
        key = _runtime_value_annotation(field.message_type.fields_by_name["key"])
        value = _runtime_value_annotation(field.message_type.fields_by_name["value"])
        return cast(Any, MutableMapping)[key, value], cast(Any, Mapping)[key, value]
    value = _runtime_value_annotation(field)
    if field.is_repeated:
        return cast(Any, MutableSequence)[value], cast(Any, Iterable)[value]
    return value, value


def _annotation_dependencies(field: FieldDescriptor) -> Iterator[str]:
    if field.type == FieldDescriptor.TYPE_ENUM and field.enum_type is not None:
        yield field.enum_type.full_name
    if field.message_type is None:
        return
    if field.message_type.is_map_entry:
        yield from _annotation_dependencies(field.message_type.fields_by_name["key"])
        yield from _annotation_dependencies(field.message_type.fields_by_name["value"])
    else:
        yield field.message_type.full_name


def _refresh_runtime_annotations(message_names: Iterable[str]) -> None:
    """Resolve runtime annotations after new message and enum types appear."""
    for full_name in message_names:
        message_type = _MESSAGES.get(full_name)
        if message_type is None:
            continue
        descriptor = message_type.__PROTO_DESCRIPTOR__
        fields = message_type.__FIELDS__
        initial_parameter_name = _INITIAL_PARAMETER_NAMES[full_name]
        parameters = [
            Parameter(
                initial_parameter_name,
                Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=SerializableMessage | None,
            ),
        ]
        annotations: dict[str, Any] = {
            initial_parameter_name: SerializableMessage | None,
            "return": type(None),
        }
        for field in fields:
            provider_field = descriptor.fields_by_name[field.proto_name]
            constructor_annotation = _constructor_annotation(provider_field)
            parameters.append(
                Parameter(
                    field.python_name,
                    Parameter.KEYWORD_ONLY,
                    default=Unset,
                    annotation=constructor_annotation,
                ),
            )
            annotations[field.python_name] = constructor_annotation
            member = message_type.__dict__.get(field.python_name)
            if isinstance(member, property):
                getter_annotation, setter_annotation = _property_annotations(provider_field)
                absent_is_none = field.oneof is not None or field.absent_is_none or field.to_python is not None
                if member.fget is not None:
                    member.fget.__annotations__ = {
                        "return": getter_annotation | None if absent_is_none else getter_annotation,
                    }
                if member.fset is not None:
                    member.fset.__annotations__ = {
                        "value": setter_annotation | None,
                        "return": type(None),
                    }
        message_type.__signature__ = Signature(parameters)  # type: ignore[attr-defined]
        message_type.__init__.__annotations__ = annotations


def message_class(
    full_name: str,
    python_name: str,
    python_fields: Mapping[str, str] | None = None,
    python_oneofs: Mapping[str, str] | None = None,
    field_documentation: Mapping[str, str] | None = None,
    oneof_documentation: Mapping[str, str] | None = None,
    *,
    message_deprecation_details: str | None = None,
    field_deprecation_details: Mapping[str, str] | None = None,
    enum_value_deprecations: Mapping[str, Mapping[int, tuple[tuple[str, str], ...]]] | None = None,
    sensitive_fields: Collection[str] = (),
    credential_fields: Collection[str] = (),
    immutable_fields: Collection[str] = (),
    immutable_oneof_fields: Collection[str] = (),
    _exported: bool = True,
) -> type[Message]:
    """Create a direct SDK message class from a registered descriptor."""
    with _CLASS_CACHE_LOCK:
        previous = _MESSAGES.get(full_name)
        if previous is not None and (not _exported or full_name in _EXPORTED_MESSAGES):
            return previous

    descriptor = REGISTRY.message_descriptor(full_name)
    field_names = dict(python_fields or {})
    oneof_names = dict(python_oneofs or {})
    field_docs = dict(field_documentation or {})
    oneof_docs = dict(oneof_documentation or {})
    field_deprecations = dict(field_deprecation_details or {})
    field_enum_value_deprecations = dict(enum_value_deprecations or {})
    fields = tuple(
        _direct_field(
            field,
            field_names.get(field.name, field.name),
            oneof_names,
            field_deprecations.get(field.name),
            field_enum_value_deprecations.get(field.name),
            sensitive=field.name in sensitive_fields,
            credentials=field.name in credential_fields,
            immutable=field.name in immutable_fields,
            immutable_oneof=field.name in immutable_oneof_fields,
            internal=not _exported,
        )
        for field in descriptor.fields
    )
    namespace: dict[str, Any] = {
        "__module__": None,
        "__PROTO_FULL_NAME__": full_name,
        "__REGISTRY__": REGISTRY,
        "__EXTENSION_REGISTRY__": _EXTENSIONS,
        "__PROTO_DESCRIPTOR__": REGISTRY.message_descriptor(full_name),
        "__PB2_DESCRIPTOR__": REGISTRY.message_descriptor(full_name),
        "__PY_TO_PB2__": {
            **{field.python_name: field.proto_name for field in fields},
            **{python_name: proto_name for proto_name, python_name in oneof_names.items()},
        },
        "__FIELDS__": fields,
        "__DEPRECATION_DETAILS__": message_deprecation_details or None,
    }

    field_python_names = {field.python_name for field in fields}
    initial_parameter_name = "initial_message"
    while initial_parameter_name in field_python_names:
        initial_parameter_name = "_" + initial_parameter_name

    def initialize(
        instance: Message,
        /,
        *initial_values: SerializableMessage | None,
        **values: object,
    ) -> None:
        if len(initial_values) > 1:
            raise TypeError(f"{python_name}() accepts at most one positional initial message")
        initial_message = initial_values[0] if initial_values else None
        if initial_parameter_name in values:
            if initial_values:
                raise TypeError(f"{python_name}() got multiple initial message values")
            candidate = values.pop(initial_parameter_name)
            initial_message = cast(SerializableMessage | None, candidate)
        cast(Any, Message.__init__)(
            instance,
            initial_message,
            **{name: value for name, value in values.items() if not isinstance(value, UnsetType)},
        )

    initialize.__name__ = "__init__"
    namespace["__init__"] = initialize

    for field in fields:
        provider_field = descriptor.fields_by_name[field.proto_name]
        getter_annotation, setter_annotation = _property_annotations(provider_field)
        absent_is_none = field.oneof is not None or field.absent_is_none or field.to_python is not None

        def get(
            self: Message,
            declaration: Field = field,
            absent: bool = absent_is_none,
        ) -> Any:
            return self._get_field(declaration, absent_is_none=absent)

        def set_value(
            self: Message,
            value: Any,
            declaration: Field = field,
        ) -> None:
            self._set_field(declaration, value)

        get.__annotations__ = {
            "return": getter_annotation | None if absent_is_none else getter_annotation,
        }
        set_value.__annotations__ = {"value": setter_annotation | None, "return": type(None)}
        namespace[field.python_name] = property(
            get,
            set_value,
            doc=field_docs.get(field.python_name),
        )

    fields_by_proto_name = {field.proto_name: field for field in fields}
    for oneof in descriptor.oneofs:
        # Protobuf represents ``optional`` proto3 fields as synthetic oneofs.
        # They have field presence, but are not part of the generated Python API.
        if len(oneof.fields) == 1 and _has_optional_keyword(oneof.fields[0]):
            continue

        proto_oneof_name = oneof.name
        oneof_name = oneof_names.get(proto_oneof_name, proto_oneof_name)
        base_name = f"__OneOfClass_{oneof_name}__"
        base = type(
            base_name,
            (OneOf,),
            {
                "__module__": None,
                "__doc__": oneof_docs.get(oneof_name),
                "name": oneof_name,
            },
        )
        namespace[base_name] = base
        selections: dict[str, type[OneOf]] = {}
        for provider_field in oneof.fields:
            declaration = fields_by_proto_name[provider_field.name]
            wrapper_name = f"__OneOfClass_{oneof_name}_{declaration.python_name}__"

            def get_oneof_value(
                self: OneOf,
                selected_field: Field = declaration,
            ) -> Any:
                return self._message._get_field(selected_field)

            wrapper = type(
                wrapper_name,
                (base,),
                {
                    "__module__": None,
                    "__doc__": field_docs.get(declaration.python_name),
                    "field": declaration.python_name,
                    "value": property(
                        get_oneof_value,
                        doc=field_docs.get(declaration.python_name),
                    ),
                },
            )
            namespace[wrapper_name] = wrapper
            selections[declaration.python_name] = wrapper

        def get_oneof(
            self: Message,
            group_name: str = oneof_name,
            wrappers: Mapping[str, type[OneOf]] = selections,
        ) -> OneOf | None:
            selected = self.which_field_in_oneof(group_name)
            if selected is None:
                return None
            try:
                wrapper_type = wrappers[selected]
            except KeyError as error:
                raise OneOfMatchError(selected) from error
            return wrapper_type(self)

        namespace[oneof_name] = property(
            get_oneof,
            doc=oneof_docs.get(oneof_name),
        )

    generated = type(python_name, (Message,), namespace)
    with _CLASS_CACHE_LOCK:
        previous = _MESSAGES.get(full_name)
        if previous is not None and (not _exported or full_name in _EXPORTED_MESSAGES):
            return previous
        # Descriptor option decoding may have created a minimal internal
        # wrapper before its public package is imported. Replace it atomically
        # with the generated names, docs, deprecations, and public codecs.
        _MESSAGES[full_name] = generated
        _INITIAL_PARAMETER_NAMES[full_name] = initial_parameter_name
        for provider_field in descriptor.fields:
            for dependency in _annotation_dependencies(provider_field):
                _ANNOTATION_DEPENDENTS.setdefault(dependency, set()).add(full_name)
        if _exported:
            _EXPORTED_MESSAGES.add(full_name)
            _refresh_runtime_annotations({full_name, *_ANNOTATION_DEPENDENTS.get(full_name, ())})
        return generated


def enum_class(
    full_name: str,
    python_name: str,
    values: Mapping[str, int],
    *,
    _exported: bool = True,
) -> type[Enum]:
    """Create an SDK enum for one registered protobuf enum."""
    with _CLASS_CACHE_LOCK:
        previous = _ENUMS.get(full_name)
        if previous is not None and (not _exported or full_name in _EXPORTED_ENUMS):
            return previous
    generated = cast(
        type[Enum],
        Enum(python_name, values, module=None),  # type: ignore[call-arg,arg-type]
    )
    setattr(generated, "__PROTO_FULL_NAME__", full_name)
    setattr(generated, "__REGISTRY__", REGISTRY)
    setattr(generated, "__PROTO_DESCRIPTOR__", REGISTRY.enum_descriptor(full_name))
    setattr(generated, "__PB2_DESCRIPTOR__", generated.__PROTO_DESCRIPTOR__)
    with _CLASS_CACHE_LOCK:
        previous = _ENUMS.get(full_name)
        if previous is not None and (not _exported or full_name in _EXPORTED_ENUMS):
            return previous
        # Replace a descriptor-only enum atomically when its public package is
        # imported with the generated class and value names.
        _ENUMS[full_name] = generated
        if _exported:
            _EXPORTED_ENUMS.add(full_name)
        _refresh_runtime_annotations(_ANNOTATION_DEPENDENTS.get(full_name, ()))
        return generated


def export_file_symbols(
    namespace: dict[str, Any],
    file_names: tuple[str, ...],
) -> list[str]:
    """Export top-level and nested symbols from registered descriptor files."""
    exports: list[str] = []

    def nested_messages(parent: type[Message], descriptor: Any, prefix: str) -> None:
        for enum_descriptor in descriptor.enum_types:
            name = prefix + "__" + enum_descriptor.name
            enum_type = enum_class(
                enum_descriptor.full_name,
                name,
                {value.name: value.number for value in enum_descriptor.values},
            )
            enum_type.__module__ = namespace["__name__"]
            namespace[name] = enum_type
            setattr(parent, enum_descriptor.name, enum_type)
        for message_descriptor in descriptor.nested_types:
            if message_descriptor.is_map_entry:
                continue
            name = prefix + "__" + message_descriptor.name
            message_type = message_class(message_descriptor.full_name, name)
            message_type.__module__ = namespace["__name__"]
            namespace[name] = message_type
            setattr(parent, message_descriptor.name, message_type)
            nested_messages(message_type, message_descriptor, name)

    for file_name in file_names:
        descriptor = REGISTRY.file_descriptor(file_name)
        for enum_descriptor in descriptor.enum_types_by_name.values():
            name = enum_descriptor.name
            enum_type = enum_class(
                enum_descriptor.full_name,
                name,
                {value.name: value.number for value in enum_descriptor.values},
            )
            enum_type.__module__ = namespace["__name__"]
            namespace[name] = enum_type
            exports.append(name)
        for message_descriptor in descriptor.message_types_by_name.values():
            if message_descriptor.is_map_entry:
                continue
            name = message_descriptor.name
            message_type = message_class(message_descriptor.full_name, name)
            message_type.__module__ = namespace["__name__"]
            namespace[name] = message_type
            exports.append(name)
            nested_messages(message_type, message_descriptor, name)
    return sorted(set(exports))


def extension(full_name: str) -> Extension[Any]:
    """Return a namespace-owned extension declaration."""
    canonical = full_name.lstrip(".")
    descriptor = REGISTRY.extension_descriptor(canonical)
    with _EXTENSION_LOCK:
        previous = _EXTENSIONS._by_name.get(canonical)
        if previous is not None:
            return previous
        extendee = descriptor.containing_type
        if extendee.full_name not in _EXTENDEES:
            _EXTENSIONS.add_extendee(extendee.full_name, extendee.extension_ranges)
            _EXTENDEES.add(extendee.full_name)
        codec = _codec_for(descriptor)
        declaration = Extension(
            _EXTENSIONS,
            canonical,
            extendee.full_name,
            descriptor.number,
            codec,
            codec.default,
            repeated=_is_repeated(descriptor),
            packed=bool(getattr(descriptor, "is_packed", False)),
        )
        _EXTENSIONS.register(declaration)
        _EXTENSION_HANDLES[canonical] = declaration
        return declaration


def register_client(full_name: str, client: type[Any]) -> None:
    """Register a generated service client for lazy operation resolution."""
    _CLIENTS[full_name.lstrip(".")] = client
