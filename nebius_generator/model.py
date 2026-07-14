"""Small linked model shared by all direct-generator partition modes."""

from __future__ import annotations

import hashlib
import keyword
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import IntEnum
from types import MappingProxyType, ModuleType
from typing import TypeVar

from . import bootstrap as descriptor_pb2
from .annotations import Annotations
from .bootstrap import FrozenMessage
from .errors import GeneratorError

T = TypeVar("T")


def generated_type_alias(full_name: str) -> str:
    """Return the collision-checked private alias for a generated value type."""
    readable = re.sub(r"[^A-Za-z0-9]", "_", full_name)
    digest = hashlib.sha256(full_name.encode()).hexdigest()[:8]
    return f"_NebiusType_{readable}_{digest}"


_MESSAGE_RUNTIME_NAMES = set(dir(object)) | {
    "_NEBIUS_UNSET",
    "_NebiusOneOf",
    "_NebiusProperty",
    "ByteSize",
    "Clear",
    "ClearField",
    "CopyFrom",
    "FindInitializationErrors",
    "FromString",
    "HasField",
    "IsInitialized",
    "MergeFrom",
    "MergeFromString",
    "ParseFromString",
    "SerializeToString",
    "WhichOneof",
    "__EXTENSION_REGISTRY__",
    "__FIELDS__",
    "Extensions",
    "__PB2_DESCRIPTOR__",
    "__PY_TO_PB2__",
    "__PROTO_DESCRIPTOR__",
    "__PROTO_FULL_NAME__",
    "__REGISTRY__",
    "__annotations__",
    "__class__",
    "__dict__",
    "__init__",
    "__module__",
    "__weakref__",
    "_bind_child",
    "_bind_mutation",
    "_check_same_type",
    "_child_changed",
    "_clear_state",
    "_closed_enum_unknown",
    "_converted_view",
    "_decode_map_entry",
    "_detach_child",
    "_extensions",
    "_field_is_default",
    "_format_map_key",
    "_fields_by_number",
    "_fields_by_proto_name",
    "_fields_by_python_name",
    "_get_field",
    "_map",
    "_mutation_suspended",
    "_notify",
    "_oneof_python_name",
    "_on_mutation",
    "_oneofs",
    "_present",
    "_record_reset",
    "_repeated",
    "_repr_field",
    "_reset_mask",
    "_reset_mask_suspended",
    "_select",
    "_set_field",
    "_suspend_mutation",
    "_suspend_reset_mask",
    "_try_decode_field",
    "_unknown_fields",
    "_values",
    "_views",
    "_write_field",
    "clear_extension",
    "from_json",
    "get_descriptor",
    "get_extension",
    "get_full_update_reset_mask",
    "get_mask",
    "has_extension",
    "is_credentials",
    "is_default",
    "is_sensitive",
    "check_presence",
    "which_field_in_oneof",
    "set_extension",
    "set_mask",
    "to_json",
}

_ENUM_RUNTIME_NAMES = (
    set(dir(object))
    | set(dir(IntEnum))
    | {
        "__annotations__",
        "__PB2_DESCRIPTOR__",
        "__PROTO_DESCRIPTOR__",
        "__PROTO_FULL_NAME__",
        "__REGISTRY__",
        "__class__",
        "__dict__",
        "__weakref__",
        "_missing_",
        "_generate_next_value_",
        "_ignore_",
        "_numeric_repr_",
        "_order_",
        "as_integer_ratio",
        "bit_count",
        "bit_length",
        "conjugate",
        "denominator",
        "from_bytes",
        "get_descriptor",
        "imag",
        "name",
        "numerator",
        "real",
        "to_bytes",
        "value",
    }
)

_CLIENT_RUNTIME_NAMES = set(dir(object)) | {
    "__annotations__",
    "__api_service_name__",
    "__PB2_DESCRIPTOR__",
    "__dict__",
    "__module__",
    "__registry__",
    "__service_deprecation_details__",
    "__service_name__",
    "__weakref__",
    "_channel",
    "get_descriptor",
    "request",
    "stream_request",
}

_COMMENT_DIRECTIVE = re.compile(
    r"^\s*(?:@exclude(?:\(([^)]*)\))?|todo|buf:lint:ignore)",
    re.IGNORECASE,
)


def _cleanup_comment(comment: str) -> str:
    result: list[str] = []
    for line in comment.split("\n"):
        match = _COMMENT_DIRECTIVE.match(line)
        if match is None:
            result.append(line.removeprefix(" "))
            continue
        exclusion = (match.group(1) if match.lastindex else "all") or "all"
        exclusion = exclusion.strip()
        if exclusion == "^":
            exclusion = "^all"
        negative = exclusion.startswith("^")
        selected = exclusion.removeprefix("^")
        tools = {item.strip() for item in selected.split(",") if item.strip()}
        excluded = bool(
            "all" in tools
            or "api" in tools
            or {"public", "api-public"}.intersection(tools)
        )
        if excluded == negative:
            result.append(_COMMENT_DIRECTIVE.sub("", line).removeprefix(" "))
    return "\n".join(result)


@dataclass
class _CommentParts:
    detached: list[str]
    leading: str = ""
    trailing: str = ""


@dataclass(frozen=True)
class Options:
    package_prefix: str = "nebius.api"
    runtime_package: str = "nebius"
    partition: str = "all"
    jobs: int = 1
    cache_dir: str | None = None

    @classmethod
    def parse(cls, parameter: str) -> "Options":
        values: dict[str, str] = {}
        for item in filter(None, parameter.split(",")):
            key, separator, value = item.partition("=")
            if not separator or not key or key in values:
                raise GeneratorError(f"invalid generator parameter {item!r}")
            values[key] = value
        supported = {
            "package_prefix",
            "runtime_package",
            "partition",
            "jobs",
            "cache_dir",
        }
        unknown = sorted(set(values) - supported)
        if unknown:
            raise GeneratorError(f"unknown generator parameter {unknown[0]!r}")
        options = cls(
            package_prefix=values.get("package_prefix", cls.package_prefix),
            runtime_package=values.get("runtime_package", cls.runtime_package),
            partition=values.get("partition", cls.partition),
            jobs=int(values.get("jobs", str(cls.jobs))),
            cache_dir=values.get("cache_dir"),
        )
        _validate_package(options.package_prefix, "package_prefix")
        _validate_package(options.runtime_package, "runtime_package")
        if options.partition not in {"all", "package", "directory"}:
            raise GeneratorError("partition must be all, package, or directory")
        if options.jobs < 1:
            raise GeneratorError("jobs must be positive")
        return options


def _validate_package(package: str, label: str) -> None:
    if not package or any(
        not part.isidentifier()
        or keyword.iskeyword(part)
        or keyword.issoftkeyword(part)
        for part in package.split(".")
    ):
        raise GeneratorError(f"invalid {label} {package!r}")


def python_name(name: str) -> str:
    """Return the conservative Python spelling for a protobuf declaration."""
    if not name.isidentifier():
        raise GeneratorError(f"invalid protobuf Python name {name!r}")
    reserved = keyword.iskeyword(name) or keyword.issoftkeyword(name)
    return name + "_" if reserved else name


@dataclass(frozen=True)
class EnumModel:
    proto: FrozenMessage
    full_name: str
    package: str
    python_qualname: str
    syntax: str
    source_file: str
    source_path: tuple[int, ...]

    @property
    def implementation_name(self) -> str:
        return self.python_qualname.replace(".", "__")


@dataclass(frozen=True)
class MessageModel:
    proto: FrozenMessage
    full_name: str
    package: str
    python_qualname: str
    syntax: str
    source_file: str
    source_path: tuple[int, ...]

    @property
    def map_entry(self) -> bool:
        return bool(self.proto.options.map_entry)

    @property
    def implementation_name(self) -> str:
        return self.python_qualname.replace(".", "__")


@dataclass(frozen=True)
class ServiceModel:
    proto: FrozenMessage
    full_name: str
    package: str
    python_name: str
    source_file: str
    source_path: tuple[int, ...]


@dataclass(frozen=True)
class ExtensionModel:
    proto: FrozenMessage
    full_name: str
    package: str
    scope: str | None
    python_name: str
    source_file: str
    source_path: tuple[int, ...]


class Graph:
    """Validated descriptor graph used by the emitter."""

    def __init__(self, request: FrozenMessage, options: Options):
        self.options = options
        files = {item.name: item for item in request.proto_file}
        if len(files) != len(request.proto_file):
            raise GeneratorError("duplicate input file name")
        missing = sorted(set(request.file_to_generate) - files.keys())
        if missing:
            raise GeneratorError(f"requested file is missing: {missing[0]}")
        self.files = MappingProxyType(files)
        self.annotations = Annotations(files)
        self._source_comments = MappingProxyType(
            {
                name: MappingProxyType(self._comments_for_file(file))
                for name, file in files.items()
            }
        )
        self.requested = frozenset(request.file_to_generate)
        (
            self.emitted_files,
            self.active_messages,
            self.active_enums,
            self.active_services,
            self.active_extensions,
        ) = self._runtime_symbols()
        self.messages: dict[str, MessageModel] = {}
        self.enums: dict[str, EnumModel] = {}
        self.services: dict[str, ServiceModel] = {}
        self.extensions: dict[str, ExtensionModel] = {}
        self._python_names: dict[tuple[str, str], str] = {}
        self._symbols: dict[str, str] = {}
        self._check_output_packages()
        self._build()
        self._check_python_collisions()

    @staticmethod
    def qualify(prefix: str, name: str) -> str:
        return f"{prefix}.{name}" if prefix else name

    def output_package(self, proto_package: str) -> str:
        suffix = proto_package or "_unpackaged"
        return f"{self.options.package_prefix}.{suffix}"

    def field_python_name(
        self,
        message: MessageModel,
        field: FrozenMessage,
    ) -> str:
        return self._python_names[("field", f"{message.full_name}.{field.name}")]

    def oneof_python_name(
        self,
        message: MessageModel,
        oneof: FrozenMessage,
    ) -> str:
        return self._python_names[("oneof", f"{message.full_name}.{oneof.name}")]

    def batch_view(self, source_files: frozenset[str]) -> "Graph":
        """Return the owned models plus compact type signatures needed by a worker."""
        view = object.__new__(Graph)
        view.options = self.options
        view.annotations = self.annotations
        view.files = MappingProxyType(
            {name: self.files[name] for name in sorted(source_files)}
        )
        view._source_comments = MappingProxyType(
            {name: self._source_comments[name] for name in sorted(source_files)}
        )
        view.requested = frozenset(
            name for name in self.requested if name in source_files
        )
        view.emitted_files = source_files
        owned_messages = {
            name: model
            for name, model in self.messages.items()
            if model.source_file in source_files
        }
        messages = dict(owned_messages)
        enums = {
            name: model
            for name, model in self.enums.items()
            if model.source_file in source_files
        }
        extensions = {
            name: model
            for name, model in self.extensions.items()
            if model.source_file in source_files
        }
        services = {
            name: model
            for name, model in self.services.items()
            if model.source_file in source_files
        }
        fields = [
            field for model in owned_messages.values() for field in model.proto.field
        ]
        fields.extend(model.proto for model in extensions.values())
        for field in tuple(fields):
            if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
                target_name = field.type_name.lstrip(".")
                target = self.messages[target_name]
                messages[target_name] = target
                if target.map_entry:
                    fields.extend(target.proto.field)
        for field in fields:
            if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
                target_name = field.type_name.lstrip(".")
                enums[target_name] = self.enums[target_name]
        for service in tuple(services.values()):
            for method in service.proto.method:
                output_name = method.output_type.lstrip(".")
                if output_name in {
                    "nebius.common.v1.Operation",
                    "nebius.common.v1alpha1.Operation",
                }:
                    operation_service_name = (
                        output_name.rsplit(".", 1)[0] + ".OperationService"
                    )
                    operation_service = self.services.get(operation_service_name)
                    if operation_service is not None:
                        services[operation_service_name] = operation_service
        for service in services.values():
            for method in service.proto.method:
                for target_name in (
                    method.input_type.lstrip("."),
                    method.output_type.lstrip("."),
                ):
                    messages[target_name] = self.messages[target_name]
        view.messages = messages
        view.enums = enums
        view.services = services
        view.extensions = extensions
        owned_prefixes = tuple(
            f"{model.full_name}."
            for collection in (
                owned_messages.values(),
                view.services.values(),
                extensions.values(),
            )
            for model in collection
            if model.source_file in source_files
        ) + tuple(f"{model.full_name}." for model in enums.values())
        view._python_names = {
            key: value
            for key, value in self._python_names.items()
            if key[1].startswith(owned_prefixes)
        }
        view._symbols = {}
        view.active_messages = frozenset(owned_messages)
        view.active_enums = frozenset(
            name for name, model in enums.items() if model.source_file in source_files
        )
        view.active_services = frozenset(view.services)
        view.active_extensions = frozenset(extensions)
        return view

    def enum_value_python_name(
        self,
        enum: EnumModel,
        value: FrozenMessage,
    ) -> str:
        return self._python_names[("enum_value", f"{enum.full_name}.{value.name}")]

    def method_python_name(
        self,
        service: ServiceModel,
        method: FrozenMessage,
    ) -> str:
        return self._python_names[("method", f"{service.full_name}.{method.name}")]

    def documentation(
        self,
        source_file: str,
        path: tuple[int, ...],
    ) -> str:
        """Return detached, leading, and trailing comments for a declaration."""
        comments = self._source_comments.get(source_file)
        return "" if comments is None else comments.get(path, "")

    def _comments_for_file(self, file: FrozenMessage) -> dict[tuple[int, ...], str]:
        comments: dict[tuple[int, ...], _CommentParts] = {}
        for location in file.source_code_info.location:
            path = tuple(location.path)
            parts = comments.setdefault(path, _CommentParts([]))
            parts.detached.extend(
                cleaned
                for comment in location.leading_detached_comments
                if (cleaned := _cleanup_comment(comment).strip())
            )
            for key, comment in (
                ("leading", location.leading_comments),
                ("trailing", location.trailing_comments),
            ):
                cleaned = _cleanup_comment(comment).strip()
                if cleaned:
                    setattr(parts, key, cleaned)

        def repair_enum(enum: FrozenMessage, path: tuple[int, ...]) -> None:
            for index in range(1, len(enum.value)):
                previous = comments.get((*path, 2, index - 1))
                current = comments.get((*path, 2, index))
                if previous or not current:
                    continue
                leading = current.leading
                trailing = current.trailing
                if leading and trailing:
                    comments[(*path, 2, index - 1)] = _CommentParts([], leading=leading)
                    current.leading = ""

        def repair_message(message: FrozenMessage, path: tuple[int, ...]) -> None:
            for index, enum in enumerate(message.enum_type):
                repair_enum(enum, (*path, 4, index))
            for index, nested in enumerate(message.nested_type):
                repair_message(nested, (*path, 3, index))

        for index, enum in enumerate(file.enum_type):
            repair_enum(enum, (5, index))
        for index, message in enumerate(file.message_type):
            repair_message(message, (4, index))

        result: dict[tuple[int, ...], str] = {}
        for path, structured in comments.items():
            values = [
                *structured.detached,
                structured.leading,
                structured.trailing,
            ]
            result[path] = "\n\n".join(str(value) for value in values if value)
        return result

    def _check_output_packages(self) -> None:
        outputs: dict[str, str] = {}
        for proto_package in sorted(
            {self.files[name].package for name in self.emitted_files}
        ):
            reserved = proto_package.split(".", 1)[0]
            if reserved in {"_registry", "_registry_fragment"}:
                raise GeneratorError(
                    f"proto package {reserved!r} conflicts with generated registry"
                )
            output = self.output_package(proto_package)
            previous = outputs.get(output)
            if previous is not None and previous != proto_package:
                raise GeneratorError(
                    f"proto packages {previous!r} and {proto_package!r} "
                    f"share output {output!r}"
                )
            outputs[output] = proto_package

    def _runtime_symbols(
        self,
    ) -> tuple[
        frozenset[str],
        frozenset[str],
        frozenset[str],
        frozenset[str],
        frozenset[str],
    ]:
        top_level: dict[str, tuple[str, str, FrozenMessage]] = {}
        owners: dict[str, str] = {}

        def claim(symbol: str, owner: str) -> None:
            previous = owners.get(symbol)
            if previous is not None:
                raise GeneratorError(f"duplicate protobuf symbol {symbol!r}")
            owners[symbol] = owner

        for file in self.files.values():

            def index_message(message: FrozenMessage, prefix: str, root: str) -> None:
                full_name = self.qualify(prefix, message.name)
                claim(full_name, root)
                for nested in message.nested_type:
                    index_message(nested, full_name, root)
                for enum in message.enum_type:
                    enum_name = self.qualify(full_name, enum.name)
                    claim(enum_name, root)

            for message in file.message_type:
                full_name = self.qualify(file.package, message.name)
                top_level[full_name] = (file.name, "message", message)
                index_message(message, file.package, full_name)
            for enum in file.enum_type:
                full_name = self.qualify(file.package, enum.name)
                top_level[full_name] = (file.name, "enum", enum)
                claim(full_name, full_name)
            for service in file.service:
                full_name = self.qualify(file.package, service.name)
                top_level[full_name] = (file.name, "service", service)
                claim(full_name, full_name)
            for extension in file.extension:
                full_name = self.qualify(file.package, extension.name)
                top_level[full_name] = (file.name, "extension", extension)
                claim(full_name, full_name)

        root_files = set(self.requested)
        for generator_runtime_file in (
            "google/protobuf/descriptor.proto",
            "google/protobuf/compiler/plugin.proto",
        ):
            if generator_runtime_file in self.files:
                root_files.add(generator_runtime_file)

        active: dict[str, set[str]] = {
            "message": set(),
            "enum": set(),
            "service": set(),
            "extension": set(),
        }
        queue: list[str] = []

        def activate(symbol: str) -> None:
            owner = owners.get(symbol.lstrip("."))
            if owner is None:
                return
            file_name, kind, _ = top_level[owner]
            del file_name
            if owner not in active[kind]:
                active[kind].add(owner)
                queue.append(owner)

        for symbol, (file_name, kind, _) in top_level.items():
            if file_name in root_files:
                active[kind].add(symbol)
                queue.append(symbol)

        def scan_message(
            message: FrozenMessage,
        ) -> Iterator[tuple[bool, FrozenMessage]]:
            yield from ((False, field) for field in message.field)
            yield from ((True, extension) for extension in message.extension)
            for nested in message.nested_type:
                yield from scan_message(nested)

        while queue:
            symbol = queue.pop()
            _, kind, declaration = top_level[symbol]
            values: Iterable[tuple[bool, FrozenMessage]]
            if kind == "message":
                values = scan_message(declaration)
            elif kind == "service":
                for method in declaration.method:
                    activate(method.input_type)
                    activate(method.output_type)
                    output_name = method.output_type.lstrip(".")
                    if output_name in {
                        "nebius.common.v1.Operation",
                        "nebius.common.v1alpha1.Operation",
                    }:
                        activate(output_name.rsplit(".", 1)[0] + ".OperationService")
                continue
            elif kind == "extension":
                activate(declaration.extendee)
                values = ((True, declaration),)
            else:
                continue
            for is_extension, value in values:
                if is_extension:
                    activate(value.extendee)
                if value.type in {
                    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                    descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
                }:
                    activate(value.type_name)

        emitted_files = frozenset(
            top_level[symbol][0] for symbols in active.values() for symbol in symbols
        )
        return (
            emitted_files,
            frozenset(active["message"]),
            frozenset(active["enum"]),
            frozenset(active["service"]),
            frozenset(active["extension"]),
        )

    def _claim(
        self,
        collection: dict[str, T],
        full_name: str,
        value: T,
        kind: str,
    ) -> None:
        self._claim_symbol(full_name, kind)
        collection[full_name] = value

    def _claim_symbol(self, full_name: str, kind: str) -> None:
        previous = self._symbols.get(full_name)
        if previous is not None:
            raise GeneratorError(
                f"duplicate protobuf symbol {full_name!r}: {previous} and {kind}"
            )
        self._symbols[full_name] = kind

    def _build(self) -> None:
        for file in sorted(
            (self.files[name] for name in self.emitted_files),
            key=lambda item: item.name,
        ):
            _validate_package(file.package, "proto package") if file.package else None
            syntax = file.syntax or "proto2"
            if syntax == "editions" or file.HasField("edition"):
                raise GeneratorError(
                    f"protobuf editions are not supported: {file.name}"
                )

            def add_enum(
                proto: FrozenMessage,
                prefix: str,
                python_prefix: str,
                source_path: tuple[int, ...],
            ) -> None:
                full_name = self.qualify(prefix, proto.name)
                class_name = self.annotations.python_name(
                    proto.options,
                    "enum",
                    python_name(proto.name),
                    "class",
                )
                qualname = self.qualify(python_prefix, class_name)
                self._claim(
                    self.enums,
                    full_name,
                    EnumModel(
                        proto,
                        full_name,
                        file.package,
                        qualname,
                        syntax,
                        file.name,
                        source_path,
                    ),
                    "enum",
                )
                value_names: set[str] = set()
                python_value_names: set[str] = set()
                for value in proto.value:
                    if value.name in value_names:
                        raise GeneratorError(f"duplicate enum value in {full_name!r}")
                    value_names.add(value.name)
                    value_python_name = self.annotations.python_name(
                        value.options,
                        "enum_value",
                        python_name(value.name),
                        "enum_value",
                    )
                    self._python_names[("enum_value", f"{full_name}.{value.name}")] = (
                        value_python_name
                    )
                    reserved_wrapped_name = value_python_name.startswith(
                        "_"
                    ) and value_python_name.endswith("_")
                    private_mangled = value_python_name.startswith(
                        "__"
                    ) and not value_python_name.endswith("__")
                    if (
                        value_python_name in python_value_names
                        or value_python_name in _ENUM_RUNTIME_NAMES
                        or reserved_wrapped_name
                        or private_mangled
                    ):
                        full_value_name = f"{full_name}.{value_python_name}"
                        raise GeneratorError(
                            f"Python enum value collision {full_value_name}"
                        )
                    python_value_names.add(value_python_name)
                    self._claim_symbol(self.qualify(prefix, value.name), "enum value")

            def add_message(
                proto: FrozenMessage,
                prefix: str,
                python_prefix: str,
                source_path: tuple[int, ...],
            ) -> None:
                full_name = self.qualify(prefix, proto.name)
                class_name = self.annotations.python_name(
                    proto.options,
                    "message",
                    python_name(proto.name),
                    "class",
                )
                qualname = self.qualify(python_prefix, class_name)
                self._claim(
                    self.messages,
                    full_name,
                    MessageModel(
                        proto,
                        full_name,
                        file.package,
                        qualname,
                        syntax,
                        file.name,
                        source_path,
                    ),
                    "message",
                )
                field_names: set[str] = set()
                field_numbers: set[int] = set()
                oneof_names = [item.name for item in proto.oneof_decl]
                if len(oneof_names) != len(set(oneof_names)):
                    raise GeneratorError(f"duplicate oneof in {full_name!r}")
                for oneof in proto.oneof_decl:
                    self._python_names[("oneof", f"{full_name}.{oneof.name}")] = (
                        self.annotations.python_name(
                            oneof.options,
                            "oneof",
                            python_name(oneof.name),
                            "field",
                        )
                    )
                for field in proto.field:
                    if field.name in field_names or field.number in field_numbers:
                        raise GeneratorError(f"duplicate field in {full_name!r}")
                    field_names.add(field.name)
                    field_numbers.add(field.number)
                    self._python_names[("field", f"{full_name}.{field.name}")] = (
                        self.annotations.python_name(
                            field.options,
                            "field",
                            python_name(field.name),
                            "field",
                        )
                    )
                    if field.HasField("oneof_index") and not (
                        0 <= field.oneof_index < len(proto.oneof_decl)
                    ):
                        raise GeneratorError(
                            f"invalid oneof index in {full_name}.{field.name}"
                        )
                    self._claim_symbol(self.qualify(full_name, field.name), "field")
                for index, nested in enumerate(proto.nested_type):
                    add_message(
                        nested,
                        full_name,
                        qualname,
                        (*source_path, 3, index),
                    )
                for index, enum in enumerate(proto.enum_type):
                    add_enum(
                        enum,
                        full_name,
                        qualname,
                        (*source_path, 4, index),
                    )
                for index, extension in enumerate(proto.extension):
                    extension_name = self.qualify(full_name, extension.name)
                    extension_python_name = self.annotations.python_name(
                        extension.options,
                        "field",
                        python_name(extension.name),
                        "field",
                    )
                    self._claim(
                        self.extensions,
                        extension_name,
                        ExtensionModel(
                            extension,
                            extension_name,
                            file.package,
                            full_name,
                            extension_python_name,
                            file.name,
                            (*source_path, 6, index),
                        ),
                        "extension",
                    )

            for index, message in enumerate(file.message_type):
                full_name = self.qualify(file.package, message.name)
                if full_name in self.active_messages:
                    add_message(message, file.package, "", (4, index))
            for index, enum in enumerate(file.enum_type):
                full_name = self.qualify(file.package, enum.name)
                if full_name in self.active_enums:
                    add_enum(enum, file.package, "", (5, index))
            for index, service in enumerate(file.service):
                full_name = self.qualify(file.package, service.name)
                if full_name not in self.active_services:
                    continue
                service_python_name = self.annotations.python_name(
                    service.options,
                    "service",
                    python_name(service.name),
                    "class",
                )
                self._claim(
                    self.services,
                    full_name,
                    ServiceModel(
                        service,
                        full_name,
                        file.package,
                        service_python_name,
                        file.name,
                        (6, index),
                    ),
                    "service",
                )
            for index, extension in enumerate(file.extension):
                full_name = self.qualify(file.package, extension.name)
                if full_name not in self.active_extensions:
                    continue
                extension_python_name = self.annotations.python_name(
                    extension.options,
                    "field",
                    python_name(extension.name),
                    "field",
                )
                self._claim(
                    self.extensions,
                    full_name,
                    ExtensionModel(
                        extension,
                        full_name,
                        file.package,
                        None,
                        extension_python_name,
                        file.name,
                        (7, index),
                    ),
                    "extension",
                )

        for message_model in self.messages.values():
            for field in message_model.proto.field:
                python_name(field.name)
                if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_GROUP:
                    full_field_name = f"{message_model.full_name}.{field.name}"
                    raise GeneratorError(f"groups are unsupported: {full_field_name}")
                if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
                    target = field.type_name.lstrip(".")
                    if target not in self.messages:
                        raise GeneratorError(
                            f"unknown message type {field.type_name!r}"
                        )
                if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
                    target = field.type_name.lstrip(".")
                    if target not in self.enums:
                        raise GeneratorError(f"unknown enum type {field.type_name!r}")
        for service_model in self.services.values():
            method_names: set[str] = set()
            for method in service_model.proto.method:
                if method.name in method_names:
                    raise GeneratorError(
                        f"duplicate method in {service_model.full_name!r}"
                    )
                method_names.add(method.name)
                self._python_names[
                    ("method", f"{service_model.full_name}.{method.name}")
                ] = self.annotations.python_name(
                    method.options,
                    "method",
                    _snake_method(method.name),
                    "method",
                )
                for target in (method.input_type, method.output_type):
                    if target.lstrip(".") not in self.messages:
                        raise GeneratorError(f"unknown RPC message type {target!r}")

    def _check_python_collisions(self) -> None:
        package_names: dict[str, dict[str, str]] = {}
        module_reserved = set(dir(ModuleType("_generated"))) | {
            "BOOL",
            "BYTES",
            "DOUBLE",
            "EXTENSIONS",
            "EXTENSION_HANDLES",
            "Enum",
            "FIXED32",
            "FIXED64",
            "FLOAT",
            "Field",
            "INT32",
            "INT64",
            "Message",
            "REGISTRY",
            "SFIXED32",
            "SFIXED64",
            "SINT32",
            "SINT64",
            "STRING",
            "UINT32",
            "UINT64",
            "enum_codec",
            "ensure_reset_mask_in_metadata",
            "message_codec",
            "_NEBIUS_TYPE_CHECKING",
            "_NEBIUS_UNSET",
            "_NEBIUS_EXPORT_SHARDS",
            "_NEBIUS_SHARD_NAMES",
            "_NebiusAttributeError",
            "_NebiusAsyncIterable",
            "_NebiusBool",
            "_NebiusBytes",
            "_NebiusClassVar",
            "_NebiusClient",
            "_NebiusClientWithOperations",
            "_NebiusDatetime",
            "_NebiusDict",
            "_NebiusExtension",
            "_NebiusEnum",
            "_NebiusField",
            "_NebiusFloat",
            "_NebiusGetattr",
            "_NebiusGlobals",
            "_NebiusInt",
            "_NebiusIsinstance",
            "_NebiusIterable",
            "_NebiusLiteral",
            "_NebiusMapping",
            "_NebiusMutableMapping",
            "_NebiusMutableSequence",
            "_NebiusOneOf",
            "_NebiusOneOfMatchError",
            "_NebiusOperation",
            "_NebiusObject",
            "_NebiusProperty",
            "_NebiusRequest",
            "_NebiusRequestKwargs",
            "_NebiusRequestStatus",
            "_NebiusSerializableMessage",
            "_NebiusSorted",
            "_NebiusStreamRequest",
            "_NebiusStreamRequestKwargs",
            "_NebiusStr",
            "_NebiusType",
            "_NebiusTypeAlias",
            "_NebiusTimedelta",
            "_NebiusUnpack",
            "_NebiusUnsetType",
            "_nebius_cast",
            "_nebius_import_module",
            "_nebius_module_dir",
            "_nebius_module_getattr",
            "_registry_fragment",
            "_nebius_datetime_to_timestamp",
            "_nebius_duration_to_timedelta",
            "_nebius_get_logger",
            "_nebius_request_status_to_status",
            "_nebius_status_to_request_status",
            "_nebius_timedelta_to_duration",
            "_nebius_timestamp_to_datetime",
            "__dir__",
            "__getattr__",
            "__all__",
            "__annotations__",
            "__builtins__",
            "__cached__",
            "__class__",
            "__doc__",
            "__dict__",
            "__file__",
            "__loader__",
            "__name__",
            "__package__",
            "__path__",
            "__spec__",
            "__weakref__",
        }

        def claim(package: str, name: str, full_name: str) -> None:
            standard_runtime_alias = package == "google.protobuf" and name in {
                "Enum",
                "Field",
            }
            if (name in module_reserved and not standard_runtime_alias) or re.fullmatch(
                r"_impl_[0-9]+", name
            ):
                raise GeneratorError(
                    f"Python symbol {full_name} shadows generated import {name}"
                )
            names = package_names.setdefault(package, {})
            previous = names.get(name)
            if previous is not None:
                raise GeneratorError(
                    f"Python symbol collision {name!r}: {previous} and {full_name}"
                )
            names[name] = full_name

        for message in self.messages.values():
            if not message.map_entry:
                claim(message.package, message.implementation_name, message.full_name)
                claim(
                    message.package,
                    generated_type_alias(message.full_name),
                    f"type alias for {message.full_name}",
                )
                for field in message.proto.field:
                    constant = re.sub(
                        r"[^A-Za-z0-9]",
                        "_",
                        f"_{message.full_name}_{field.name}",
                    ).upper()
                    claim(
                        message.package,
                        constant,
                        f"{message.full_name}.{field.name}",
                    )
        for enum in self.enums.values():
            claim(
                enum.package,
                enum.python_qualname.replace(".", "__"),
                enum.full_name,
            )
            claim(
                enum.package,
                generated_type_alias(enum.full_name),
                f"type alias for {enum.full_name}",
            )
        for service in self.services.values():
            claim(
                service.package,
                service.python_name + "Client",
                service.full_name,
            )
        for extension in self.extensions.values():
            if extension.scope is None:
                claim(
                    extension.package,
                    extension.python_name,
                    extension.full_name,
                )

        emitted_packages = {
            *(item.package for item in self.messages.values() if not item.map_entry),
            *(item.package for item in self.enums.values()),
            *(item.package for item in self.services.values()),
            *(item.package for item in self.extensions.values()),
        }
        output_packages = {
            package: self.output_package(package) for package in emitted_packages
        }
        for parent, parent_output in output_packages.items():
            descendants: set[str] = set()
            for child, child_output in output_packages.items():
                if child == parent or not child_output.startswith(parent_output + "."):
                    continue
                descendant = child_output[len(parent_output) + 1 :].split(".", 1)[0]
                if descendant in descendants:
                    continue
                descendants.add(descendant)
                claim(parent, descendant, f"subpackage {child_output}")

        scoped_extensions: dict[str, list[ExtensionModel]] = {}
        for extension in self.extensions.values():
            if extension.scope is not None:
                scoped_extensions.setdefault(extension.scope, []).append(extension)
        for message in self.messages.values():
            python_fields: dict[str, str] = {}
            for field in message.proto.field:
                name = self.field_python_name(message, field)
                private_mangled = name.startswith("__") and not name.endswith("__")
                if (
                    name in _MESSAGE_RUNTIME_NAMES
                    or name in python_fields
                    or private_mangled
                ):
                    raise GeneratorError(
                        f"Python field collision {message.full_name}.{name}"
                    )
                python_fields[name] = field.name
            python_oneofs: dict[str, str] = {}
            for oneof in message.proto.oneof_decl:
                name = self.oneof_python_name(message, oneof)
                if (
                    name in python_oneofs
                    or name in python_fields
                    or name in python_fields.values()
                    or name in _MESSAGE_RUNTIME_NAMES
                ):
                    raise GeneratorError(
                        f"Python oneof collision {message.full_name}.{name}"
                    )
                python_oneofs[name] = oneof.name
            proto_oneofs = {
                proto_name: python_name
                for python_name, proto_name in python_oneofs.items()
            }
            for python_name, proto_name in python_oneofs.items():
                other_python_name = proto_oneofs.get(python_name)
                if other_python_name is not None and other_python_name != python_name:
                    raise GeneratorError(
                        f"Python oneof collision {message.full_name}.{python_name}: "
                        f"generated from {proto_name} and protobuf oneof {python_name}"
                    )
            child_names = {
                self.messages[
                    f"{message.full_name}.{item.name}"
                ].python_qualname.rsplit(".", 1)[-1]
                for item in message.proto.nested_type
            }
            child_names.update(
                self.enums[f"{message.full_name}.{item.name}"].python_qualname.rsplit(
                    ".", 1
                )[-1]
                for item in message.proto.enum_type
            )
            extension_owners: dict[str, str] = {}
            for item in scoped_extensions.get(message.full_name, ()):
                previous = extension_owners.get(item.python_name)
                if previous is not None:
                    raise GeneratorError(
                        f"Python scoped extension collision {message.full_name}."
                        f"{item.python_name}: {previous} and {item.full_name}"
                    )
                extension_owners[item.python_name] = item.full_name
            extension_names = set(extension_owners)
            attachment_runtime_names = {
                generated_type_alias(
                    self.messages[f"{message.full_name}.{item.name}"].full_name
                )
                for item in message.proto.nested_type
                if not item.options.map_entry
            }
            attachment_runtime_names.update(
                generated_type_alias(
                    self.enums[f"{message.full_name}.{item.name}"].full_name
                )
                for item in message.proto.enum_type
            )
            generated_oneof_owners: dict[str, str] = {}

            def claim_oneof_helper(name: str, owner: str) -> None:
                previous = generated_oneof_owners.get(name)
                if previous is not None:
                    raise GeneratorError(
                        f"Python oneof helper collision {message.full_name}.{name}: "
                        f"{previous} and {owner}"
                    )
                generated_oneof_owners[name] = owner

            for index, oneof in enumerate(message.proto.oneof_decl):
                oneof_name = self.oneof_python_name(message, oneof)
                claim_oneof_helper(
                    f"__OneOfClass_{oneof_name}__", f"oneof {oneof.name}"
                )
                for field in message.proto.field:
                    if not field.HasField("oneof_index") or field.oneof_index != index:
                        continue
                    field_name = self.field_python_name(message, field)
                    claim_oneof_helper(
                        f"__OneOfClass_{oneof_name}_{field_name}__",
                        f"field {field.name}",
                    )
            generated_oneof_names = set(generated_oneof_owners)
            runtime_collisions = (child_names | extension_names) & (
                _MESSAGE_RUNTIME_NAMES | attachment_runtime_names
            )
            if runtime_collisions:
                raise GeneratorError(
                    f"Python member collision {message.full_name}."
                    f"{min(runtime_collisions)}"
                )
            collisions = set(python_fields) & (
                child_names | extension_names | generated_oneof_names
            )
            collisions |= child_names & extension_names
            collisions |= set(python_oneofs) & (child_names | extension_names)
            collisions |= generated_oneof_names & (child_names | extension_names)
            if collisions:
                raise GeneratorError(
                    f"Python member collision {message.full_name}.{min(collisions)}"
                )
        for service in self.services.values():
            names: set[str] = set(_CLIENT_RUNTIME_NAMES)
            for method in service.proto.method:
                name = self.method_python_name(service, method)
                private_mangled = name.startswith("__") and not name.endswith("__")
                if name in names or private_mangled:
                    raise GeneratorError(
                        f"Python method collision {service.full_name}.{name}"
                    )
                names.add(name)


def _snake_method(name: str) -> str:
    name = re.sub(r"(?<=[A-Z])([A-Z][a-z])", r"_\1", name)
    name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return python_name(name.lower())
