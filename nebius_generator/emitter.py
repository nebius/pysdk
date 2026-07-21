"""Deterministic Python emitter for direct protobuf classes."""

from __future__ import annotations

import ast
import hashlib
import math
import re
from collections.abc import Iterable

from . import bootstrap as descriptor_pb2
from .bootstrap import FrozenMessage, GeneratedFile, serialize_file_descriptor
from .docs import markdown_to_rst
from .errors import GeneratorError
from .model import (
    EnumModel,
    ExtensionModel,
    Graph,
    MessageModel,
    ServiceModel,
)
from .model import (
    generated_type_alias as _named_alias,
)

_SCALAR_CODECS = {
    descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE: "DOUBLE",
    descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT: "FLOAT",
    descriptor_pb2.FieldDescriptorProto.TYPE_INT64: "INT64",
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT64: "UINT64",
    descriptor_pb2.FieldDescriptorProto.TYPE_INT32: "INT32",
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64: "FIXED64",
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32: "FIXED32",
    descriptor_pb2.FieldDescriptorProto.TYPE_BOOL: "BOOL",
    descriptor_pb2.FieldDescriptorProto.TYPE_STRING: "STRING",
    descriptor_pb2.FieldDescriptorProto.TYPE_BYTES: "BYTES",
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT32: "UINT32",
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32: "SFIXED32",
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64: "SFIXED64",
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT32: "SINT32",
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT64: "SINT64",
}

_SCALAR_TYPES = {
    descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE: "_NebiusFloat",
    descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT: "_NebiusFloat",
    descriptor_pb2.FieldDescriptorProto.TYPE_INT64: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT64: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_INT32: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_BOOL: "_NebiusBool",
    descriptor_pb2.FieldDescriptorProto.TYPE_STRING: "_NebiusStr",
    descriptor_pb2.FieldDescriptorProto.TYPE_BYTES: "_NebiusBytes",
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT32: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT32: "_NebiusInt",
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT64: "_NebiusInt",
}

_WKT_VIEW_TYPES = {
    "google.protobuf.Timestamp": "_NebiusDatetime",
    "google.protobuf.Duration": "_NebiusTimedelta",
    "google.rpc.Status": "_NebiusRequestStatus",
}

_OPERATION_SERVICES = {
    "nebius.common.v1.Operation": "nebius.common.v1.OperationService",
    "nebius.common.v1alpha1.Operation": "nebius.common.v1alpha1.OperationService",
}


def _documentation(
    graph: Graph,
    source_file: str,
    source_path: tuple[int, ...],
    *,
    deprecation_summary: str = "",
    additional: str = "",
) -> str:
    return "\n\n".join(
        part
        for part in (
            markdown_to_rst(graph.documentation(source_file, source_path)).strip(),
            deprecation_summary,
            additional,
        )
        if part
    )


def _append_docstring(lines: list[str], indent: str, documentation: str) -> None:
    if documentation:
        lines.append(f"{indent}{documentation!r}")


def _warning(subject: str, full_name: str, summary: str, indent: str) -> str:
    return (
        f"{indent}_nebius_get_logger('deprecation').warning("
        f"{f'{subject} {full_name} is deprecated. {summary}'!r}, "
        "stack_info=True, stacklevel=2)"
    )


def _constant(full_name: str, field_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "_", f"_{full_name}_{field_name}").upper()


def _enum_codec(enum: EnumModel) -> str:
    values = tuple(value.number for value in enum.proto.value)
    if not values:
        raise GeneratorError(f"enum has no values: {enum.full_name}")
    names = {value.name: value.number for value in enum.proto.value}
    return (
        f"enum_codec({values!r}, default={values[0]!r}, "
        f"closed={enum.syntax == 'proto2'!r}, names={names!r}, "
        f"enum_type=lambda: REGISTRY.enum_class({enum.full_name!r}))"
    )


def _codec(field: FrozenMessage, graph: Graph) -> str:
    if field.type in _SCALAR_CODECS:
        return _SCALAR_CODECS[field.type]
    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
        target = field.type_name.lstrip(".")
        return f"message_codec(lambda: REGISTRY.message_class({target!r}))"
    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
        return _enum_codec(graph.enums[field.type_name.lstrip(".")])
    raise GeneratorError(f"unsupported field type {field.type}")


def _c_unescape(text: str) -> bytes:
    escapes = {
        "a": 7,
        "b": 8,
        "f": 12,
        "n": 10,
        "r": 13,
        "t": 9,
        "v": 11,
        "\\": 92,
        "?": 63,
        "'": 39,
        '"': 34,
    }
    result = bytearray()
    index = 0
    while index < len(text):
        if text[index] != "\\":
            result.extend(text[index].encode())
            index += 1
            continue
        index += 1
        if index == len(text):
            raise GeneratorError("unterminated bytes default escape")
        escaped = text[index]
        index += 1
        if escaped in escapes:
            result.append(escapes[escaped])
        elif escaped in "01234567":
            digits = escaped
            while index < len(text) and len(digits) < 3 and text[index] in "01234567":
                digits += text[index]
                index += 1
            result.append(int(digits, 8) & 0xFF)
        elif escaped == "x":
            start = index
            while index < len(text) and text[index] in "0123456789abcdefABCDEF":
                index += 1
            if index == start:
                raise GeneratorError("empty hex bytes default escape")
            value = int(text[start:index], 16)
            if value > 0xFF:
                raise GeneratorError("hex bytes default escape exceeds 8 bits")
            result.append(value)
        else:
            raise GeneratorError(f"unknown bytes default escape \\{escaped}")
    return bytes(result)


def _default(
    field: FrozenMessage,
    graph: Graph,
) -> object:
    text = field.default_value
    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_STRING:
        return text
    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_BYTES:
        return _c_unescape(text)
    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_BOOL:
        return text == "true"
    if field.type in {
        descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT,
        descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE,
    }:
        if text == "inf":
            return math.inf
        if text == "-inf":
            return -math.inf
        if text == "nan":
            return math.nan
        return float(text)
    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
        enum = graph.enums[field.type_name.lstrip(".")]
        return next(value.number for value in enum.proto.value if value.name == text)
    sign = -1 if text.startswith("-") else 1
    unsigned = text[1:] if text[:1] in {"-", "+"} else text
    if unsigned.lower().startswith("0x"):
        return sign * int(unsigned[2:], 16)
    if len(unsigned) > 1 and unsigned.startswith("0"):
        return sign * int(unsigned, 8)
    return sign * int(unsigned, 10)


def _literal(value: object) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "float('nan')"
        if value == math.inf:
            return "float('inf')"
        if value == -math.inf:
            return "float('-inf')"
    return repr(value)


def _field_expression(
    message: MessageModel,
    field: FrozenMessage,
    graph: Graph,
    runtime_field: str = "Field",
) -> str:
    codec = _codec(field, graph)
    map_key_codec: str | None = None
    if field.type == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
        target = graph.messages[field.type_name.lstrip(".")]
        if target.map_entry:
            if len(target.proto.field) != 2:
                raise GeneratorError(f"invalid map entry {target.full_name}")
            map_key_codec = _codec(target.proto.field[0], graph)
            codec = _codec(target.proto.field[1], graph)
    oneof = (
        graph.oneof_python_name(
            message,
            message.proto.oneof_decl[field.oneof_index],
        )
        if field.HasField("oneof_index")
        else None
    )
    repeated = (
        field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
        and map_key_codec is None
    )
    packable = field.type not in {
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        descriptor_pb2.FieldDescriptorProto.TYPE_BYTES,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
    }
    packed = (
        repeated
        and packable
        and (
            field.options.packed
            if field.options.HasField("packed")
            else message.syntax == "proto3"
        )
    )
    arguments = [
        repr(field.name),
        repr(graph.field_python_name(message, field)),
        repr(field.number),
        codec,
    ]
    keywords: list[str] = []
    if repeated:
        keywords.append("repeated=True")
    if packed:
        keywords.append("packed=True")
    if message.syntax == "proto2" or field.proto3_optional:
        keywords.append("explicit_presence=True")
    if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REQUIRED:
        keywords.append("required=True")
    if oneof is not None:
        keywords.append(f"oneof={oneof!r}")
    if field.json_name:
        keywords.append(f"json_name={field.json_name!r}")
    if field.HasField("default_value"):
        default = _literal(_default(field, graph))
        keywords.append(f"default_factory=lambda: {default}")
    if map_key_codec is not None:
        keywords.append(f"map_key_codec={map_key_codec}")
    if graph.annotations.sensitive(field.options):
        keywords.append("sensitive=True")
    if graph.annotations.credentials(field.options):
        keywords.append("credentials=True")
    target_name = (
        graph.messages[field.type_name.lstrip(".")].proto.field[1].type_name
        if map_key_codec is not None
        else field.type_name
    ).lstrip(".")
    if target_name == "google.protobuf.Timestamp":
        keywords.extend(
            (
                "to_python=_nebius_timestamp_to_datetime",
                "from_python=lambda value: _nebius_datetime_to_timestamp("
                "value, lambda: REGISTRY.message_class("
                f"{target_name!r}))",
            )
        )
    elif target_name == "google.protobuf.Duration":
        keywords.extend(
            (
                "to_python=_nebius_duration_to_timedelta",
                "from_python=lambda value: _nebius_timedelta_to_duration("
                "value, lambda: REGISTRY.message_class("
                f"{target_name!r}))",
            )
        )
    elif target_name == "google.rpc.Status":
        keywords.extend(
            (
                "to_python=_nebius_status_to_request_status",
                "from_python=lambda value: _nebius_request_status_to_status("
                "value, lambda: REGISTRY.message_class("
                f"{target_name!r}))",
            )
        )
    return f"{runtime_field}({', '.join([*arguments, *keywords])})"


def _relative_registry(package: str, prefix: str) -> str:
    suffix = package.removeprefix(prefix + ".")
    return "." * (len(suffix.split(".")) + 1) + "_registry"


def _type_alias(package: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9]", "_", package)
    digest = hashlib.sha256(package.encode()).hexdigest()[:8]
    return f"_type_{readable}_{digest}"


def _relative_type_import(current: str, target: str, alias: str) -> str:
    current_parts = current.split(".")
    target_parts = target.split(".")
    target_parent = target_parts[:-1]
    common = 0
    for current_part, target_part in zip(current_parts, target_parent):
        if current_part != target_part:
            break
        common += 1
    if common == 0:
        raise GeneratorError(
            f"cannot import generated package {target!r} from {current!r}"
        )
    level = len(current_parts) - common + 1
    module = "." * level + ".".join(target_parent[common:])
    return f"from {module} import {target_parts[-1]} as {alias}"


def _local_name(base: str, used: set[str]) -> str:
    name = base
    while name in used:
        name += "_"
    used.add(name)
    return name


def _named_type(full_name: str, package: str, graph: Graph) -> str:
    name = full_name.lstrip(".")
    target = graph.messages.get(name) or graph.enums.get(name)
    if target is None:
        raise GeneratorError(f"unknown field type {full_name!r}")
    if target.package == package:
        return _named_alias(target.full_name)
    return f"{_type_alias(target.package)}.{target.python_qualname}"


def _service_type(full_name: str, package: str, graph: Graph) -> str:
    target = graph.services.get(full_name.lstrip("."))
    if target is None:
        raise GeneratorError(f"unknown service type {full_name!r}")
    name = target.python_name + "Client"
    if target.package == package:
        return name
    return f"{_type_alias(target.package)}.{name}"


def _value_type(field: FrozenMessage, package: str, graph: Graph) -> str:
    if field.type in _SCALAR_TYPES:
        return _SCALAR_TYPES[field.type]
    if field.type in {
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
    }:
        view_type = _WKT_VIEW_TYPES.get(field.type_name.lstrip("."))
        if view_type is not None:
            return view_type
        return _named_type(field.type_name, package, graph)
    raise GeneratorError(f"unsupported field type {field.type}")


def _raw_value_type(field: FrozenMessage, package: str, graph: Graph) -> str:
    if field.type in _SCALAR_TYPES:
        return _SCALAR_TYPES[field.type]
    if field.type in {
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
    }:
        return _named_type(field.type_name, package, graph)
    raise GeneratorError(f"unsupported field type {field.type}")


def _setter_value_type(field: FrozenMessage, package: str, graph: Graph) -> str:
    view_type = _value_type(field, package, graph)
    raw_type = _raw_value_type(field, package, graph)
    return view_type if view_type == raw_type else f"{view_type} | {raw_type}"


def _map_fields(
    field: FrozenMessage, graph: Graph
) -> tuple[FrozenMessage, FrozenMessage] | None:
    if field.type != descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE:
        return None
    target = graph.messages[field.type_name.lstrip(".")]
    if not target.map_entry:
        return None
    if len(target.proto.field) != 2:
        raise GeneratorError(f"invalid map entry {target.full_name}")
    return target.proto.field[0], target.proto.field[1]


def _getter_type(field: FrozenMessage, package: str, graph: Graph) -> str:
    map_fields = _map_fields(field, graph)
    if map_fields is not None:
        key_field, value_field = map_fields
        key_type = _value_type(key_field, package, graph)
        value_type = _value_type(value_field, package, graph)
        return f"_NebiusMutableMapping[{key_type}, {value_type}]"
    value_type = _value_type(field, package, graph)
    if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
        return f"_NebiusMutableSequence[{value_type}]"
    if (
        field.HasField("oneof_index")
        or field.proto3_optional
        or field.type_name.lstrip(".") in _WKT_VIEW_TYPES
    ):
        return f"{value_type} | None"
    return value_type


def _setter_type(field: FrozenMessage, package: str, graph: Graph) -> str:
    map_fields = _map_fields(field, graph)
    if map_fields is not None:
        key_field, value_field = map_fields
        key_type = _setter_value_type(key_field, package, graph)
        value_type = _setter_value_type(value_field, package, graph)
        result: str = f"_NebiusMapping[{key_type}, {value_type}]"
    else:
        value_type = _setter_value_type(field, package, graph)
        result = (
            f"_NebiusIterable[{value_type}]"
            if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
            else value_type
        )
    return f"{result} | None"


def _extension_type(field: FrozenMessage, package: str, graph: Graph) -> str:
    value_type = _raw_value_type(field, package, graph)
    if field.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED:
        return f"_NebiusMutableSequence[{value_type}]"
    return value_type


def _referenced_type_packages(
    package: str,
    messages: Iterable[MessageModel],
    services: Iterable[ServiceModel],
    extensions: Iterable[ExtensionModel],
    graph: Graph,
) -> tuple[str, ...]:
    names: list[str] = []
    for message in messages:
        for field in message.proto.field:
            map_fields = _map_fields(field, graph)
            fields = map_fields or (field,)
            names.extend(
                item.type_name.lstrip(".")
                for item in fields
                if item.type
                in {
                    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                    descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
                }
            )
    for service in services:
        for method in service.proto.method:
            names.extend(
                (method.input_type.lstrip("."), method.output_type.lstrip("."))
            )
    for extension in extensions:
        field = extension.proto
        if field.type in {
            descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
            descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        }:
            names.append(field.type_name.lstrip("."))
    packages: set[str] = set()
    for name in names:
        target = graph.messages.get(name) or graph.enums.get(name)
        if target is None:
            raise GeneratorError(f"unknown referenced type {name!r}")
        packages.add(target.package)
    packages.discard(package)
    return tuple(sorted(packages))


def _type_import_lines(
    package: str,
    messages: Iterable[MessageModel],
    services: Iterable[ServiceModel],
    extensions: Iterable[ExtensionModel],
    graph: Graph,
) -> list[str]:
    messages = tuple(messages)
    services = tuple(services)
    extensions = tuple(extensions)
    output_package = graph.output_package(package)
    type_packages = _referenced_type_packages(
        package, messages, services, extensions, graph
    )
    runtime_type_packages = {
        graph.messages[method.output_type.lstrip(".")].package
        for service in services
        for method in service.proto.method
        if method.output_type.lstrip(".") in _OPERATION_SERVICES
        and graph.messages[method.output_type.lstrip(".")].package != package
    }

    lines: list[str] = []
    for target_package in sorted(runtime_type_packages):
        lines.append(
            _relative_type_import(
                output_package,
                graph.output_package(target_package),
                _type_alias(target_package),
            )
        )
    typing_only_packages = set(type_packages) - runtime_type_packages
    if typing_only_packages:
        lines.append("if _NEBIUS_TYPE_CHECKING:")
        for target_package in sorted(typing_only_packages):
            lines.append(
                "    "
                + _relative_type_import(
                    output_package,
                    graph.output_package(target_package),
                    _type_alias(target_package),
                )
            )
        lines.append("")
    return lines


def _message_source(message: MessageModel, graph: Graph) -> list[str]:
    lines = [f"class {message.implementation_name}(Message):"]
    message_deprecation = graph.annotations.deprecation(
        message.proto.options, "message"
    )
    message_summary = (
        message_deprecation.summary() if message_deprecation is not None else ""
    )
    _append_docstring(
        lines,
        "    ",
        _documentation(
            graph,
            message.source_file,
            message.source_path,
            deprecation_summary=message_summary,
        ),
    )
    lines.extend(
        [
            f"    __PROTO_FULL_NAME__ = {message.full_name!r}",
            "    __REGISTRY__ = REGISTRY",
            "    __EXTENSION_REGISTRY__ = EXTENSIONS",
            "    __PROTO_DESCRIPTOR__ = "
            f"REGISTRY.message_descriptor({message.full_name!r})",
            "    __PB2_DESCRIPTOR__ = __PROTO_DESCRIPTOR__",
        ]
    )
    if not message.proto.field:
        lines.append("    pass")
    for nested in message.proto.nested_type:
        message_target = graph.messages[f"{message.full_name}.{nested.name}"]
        if not message_target.map_entry:
            child = message_target.python_qualname.rsplit(".", 1)[-1]
            lines.append(
                f"    {child}: _NebiusTypeAlias = "
                f"{_named_alias(message_target.full_name)}"
            )
    for nested in message.proto.enum_type:
        enum_target = graph.enums[f"{message.full_name}.{nested.name}"]
        child = enum_target.python_qualname.rsplit(".", 1)[-1]
        lines.append(
            f"    {child}: _NebiusTypeAlias = {_named_alias(enum_target.full_name)}"
        )
    for extension in sorted(
        (item for item in graph.extensions.values() if item.scope == message.full_name),
        key=lambda item: item.full_name,
    ):
        lines.append(
            f"    {extension.python_name}: _NebiusClassVar[_NebiusExtension["
            f"{_extension_type(extension.proto, message.package, graph)}]]"
        )
    for index, oneof in enumerate(message.proto.oneof_decl):
        oneof_name = graph.oneof_python_name(message, oneof)
        fields = [
            field
            for field in message.proto.field
            if field.HasField("oneof_index") and field.oneof_index == index
        ]
        if not fields:
            continue
        base_name = f"__OneOfClass_{oneof_name}__"
        lines.extend(
            [
                "",
                f"    class {base_name}(_NebiusOneOf):",
                f"        name: str = {oneof.name!r}",
            ]
        )
        wrappers: list[str] = []
        for field in fields:
            field_name = graph.field_python_name(message, field)
            wrapper = f"__OneOfClass_{oneof_name}_{field_name}__"
            field_type = _value_type(field, message.package, graph)
            field_constant = _constant(message.full_name, field.name)
            wrappers.append(wrapper)
            lines.extend(
                [
                    "",
                    f"    class {wrapper}({base_name}):",
                    f"        field: _NebiusLiteral[{field_name!r}] = {field_name!r}",
                    "",
                    "        @_NebiusProperty",
                    f"        def value(self) -> {field_type}:",
                    "            return _nebius_cast("
                    f"{field_type!r}, "
                    f"self._message._get_field({field_constant}),"
                    ")",
                ]
            )
        union = " | ".join(wrappers) if wrappers else "None"
        lines.extend(
            [
                "",
                "    @_NebiusProperty",
                f"    def {oneof_name}(self) -> {union} | None:",
                f"        selected = self.which_field_in_oneof({oneof_name!r})",
                "        match selected:",
            ]
        )
        for field, wrapper in zip(fields, wrappers):
            field_name = graph.field_python_name(message, field)
            lines.extend(
                [
                    f"            case {field_name!r}:",
                    f"                return self.{wrapper}(self)",
                ]
            )
        lines.extend(
            [
                "            case None:",
                "                return None",
                "            case _:",
                "                raise _NebiusOneOfMatchError(selected)",
            ]
        )
    constructor_fields = list(message.proto.field)
    used_names = {
        graph.field_python_name(message, field) for field in constructor_fields
    }
    self_name = _local_name("self", used_names)
    initial_name = _local_name("initial_message", used_names)
    values_name = _local_name("values", used_names)
    signature = [
        "",
        "    def __init__(",
        f"        {self_name},",
        f"        {initial_name}: _NebiusSerializableMessage | None = None,",
    ]
    if constructor_fields:
        signature.append("        *,")
        for field in constructor_fields:
            name = graph.field_python_name(message, field)
            setter_type = _setter_type(field, message.package, graph)
            signature.append(
                f"        {name}: {setter_type} | _NebiusUnsetType = " "_NEBIUS_UNSET,"
            )
    signature.extend(
        [
            "    ) -> None:",
            f"        {values_name}: _NebiusDict[_NebiusStr, _NebiusObject] = {{}}",
        ]
    )
    if message_deprecation is not None:
        signature.append(
            _warning("Message", message.full_name, message_summary, "        ")
        )
    for field in constructor_fields:
        name = graph.field_python_name(message, field)
        signature.append(f"        if {name} is not _NEBIUS_UNSET:")
        field_deprecation = graph.annotations.deprecation(field.options, "field")
        if field_deprecation is not None:
            signature.append(
                _warning(
                    "Field",
                    f"{message.full_name}.{field.name}",
                    field_deprecation.summary(),
                    "            ",
                )
            )
        if (
            field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM
            and field.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
        ):
            enum = graph.enums[field.type_name.lstrip(".")]
            enum_type = _named_type(field.type_name, message.package, graph)
            for enum_value in enum.proto.value:
                value_deprecation = graph.annotations.deprecation(
                    enum_value.options, "enum_value"
                )
                if value_deprecation is None:
                    continue
                value_name = graph.enum_value_python_name(enum, enum_value)
                signature.append(f"            if {name} == {enum_type}.{value_name}:")
                signature.append(
                    _warning(
                        "Setting deprecated enum value",
                        f"{enum.full_name}.{enum_value.name} for field "
                        f"{message.full_name}.{field.name}",
                        value_deprecation.summary(),
                        "                ",
                    )
                )
        signature.append(f"            {values_name}[{name!r}] = {name}")
    signature.append(f"        super().__init__({initial_name}, **{values_name})")
    lines.extend(signature)
    for field in constructor_fields:
        name = graph.field_python_name(message, field)
        constant = _constant(message.full_name, field.name)
        getter_type = _getter_type(field, message.package, graph)
        setter_type = _setter_type(field, message.package, graph)
        absent_is_none = (
            field.HasField("oneof_index")
            or field.proto3_optional
            or (
                field.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                and field.type_name.lstrip(".") in _WKT_VIEW_TYPES
            )
        )
        field_index = message.proto.field.index(field)
        field_deprecation = graph.annotations.deprecation(field.options, "field")
        field_summary = (
            field_deprecation.summary() if field_deprecation is not None else ""
        )
        lines.extend(
            [
                "",
                "    @_NebiusProperty",
                f"    def {name}(self) -> {getter_type}:",
            ]
        )
        _append_docstring(
            lines,
            "        ",
            _documentation(
                graph,
                message.source_file,
                (*message.source_path, 2, field_index),
                deprecation_summary=field_summary,
            ),
        )
        if field_deprecation is not None:
            lines.append(
                _warning(
                    "Field",
                    f"{message.full_name}.{field.name}",
                    field_summary,
                    "        ",
                )
            )
        lines.extend(
            (
                f"        value = self._get_field({constant}, "
                f"absent_is_none={absent_is_none!r})",
            )
        )
        if (
            field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM
            and field.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
        ):
            enum_name = field.type_name.lstrip(".")
            lines.append(
                f"        return _nebius_cast({getter_type!r}, "
                "None if value is None else "
                f"REGISTRY.enum_class({enum_name!r})(value))"
            )
        else:
            lines.append(f"        return _nebius_cast({getter_type!r}, value)")
        lines.extend(
            [
                "",
                f"    @{name}.setter",
                f"    def {name}(self, value: {setter_type}) -> None:",
            ]
        )
        if field_deprecation is not None:
            lines.append(
                _warning(
                    "Field",
                    f"{message.full_name}.{field.name}",
                    field_summary,
                    "        ",
                )
            )
        if (
            field.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM
            and field.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
        ):
            enum = graph.enums[field.type_name.lstrip(".")]
            enum_type = _named_type(field.type_name, message.package, graph)
            for enum_value in enum.proto.value:
                value_deprecation = graph.annotations.deprecation(
                    enum_value.options, "enum_value"
                )
                if value_deprecation is None:
                    continue
                value_name = graph.enum_value_python_name(enum, enum_value)
                lines.append(f"        if value == {enum_type}.{value_name}:")
                lines.append(
                    _warning(
                        "Setting deprecated enum value",
                        f"{enum.full_name}.{enum_value.name} for field "
                        f"{message.full_name}.{field.name}",
                        value_deprecation.summary(),
                        "            ",
                    )
                )
        lines.append(f"        self._set_field({constant}, value)")
    mappings = {
        graph.field_python_name(message, field): field.name
        for field in constructor_fields
    }
    mappings.update(
        {
            graph.oneof_python_name(message, oneof): oneof.name
            for oneof in message.proto.oneof_decl
            if any(
                field.HasField("oneof_index")
                and field.oneof_index == message.proto.oneof_decl.index(oneof)
                and field in constructor_fields
                for field in message.proto.field
            )
        }
    )
    mappings.update(
        {
            graph.messages[f"{message.full_name}.{nested.name}"].python_qualname.rsplit(
                ".", 1
            )[-1]: nested.name
            for nested in message.proto.nested_type
        }
    )
    mappings.update(
        {
            graph.enums[f"{message.full_name}.{nested.name}"].python_qualname.rsplit(
                ".", 1
            )[-1]: nested.name
            for nested in message.proto.enum_type
        }
    )
    lines.extend(["", f"    __PY_TO_PB2__ = {mappings!r}"])
    return lines


_PACKAGE_SECTIONS = (
    "type_imports",
    "enums",
    "messages",
    "fields",
    "attachments",
    "extensions",
    "services",
    "exports",
)

_SHARD_LINE_LIMIT = 5_000


def _package_source(
    package: str, graph: Graph, source_files: frozenset[str] | None = None
) -> str:
    def selected(
        item: MessageModel | EnumModel | ServiceModel | ExtensionModel,
    ) -> bool:
        return source_files is None or item.source_file in source_files

    messages = sorted(
        (
            item
            for item in graph.messages.values()
            if item.package == package and not item.map_entry and selected(item)
        ),
        key=lambda item: (-item.python_qualname.count("."), item.full_name),
    )
    enums = sorted(
        (
            item
            for item in graph.enums.values()
            if item.package == package and selected(item)
        ),
        key=lambda item: item.full_name,
    )
    services = sorted(
        (
            item
            for item in graph.services.values()
            if item.package == package and selected(item)
        ),
        key=lambda item: item.full_name,
    )
    extensions = sorted(
        (
            item
            for item in graph.extensions.values()
            if item.package == package and selected(item)
        ),
        key=lambda item: item.full_name,
    )
    output_package = graph.output_package(package)
    registry_import = _relative_registry(output_package, graph.options.package_prefix)
    runtime = graph.options.runtime_package
    package_implementations: set[str] = set()
    if package == "google.protobuf":
        package_implementations.update(
            item.implementation_name
            for item in graph.messages.values()
            if item.package == package
        )
        package_implementations.update(
            item.implementation_name
            for item in graph.enums.values()
            if item.package == package
        )
    field_collision = "Field" in package_implementations
    enum_collision = "Enum" in package_implementations
    field_import = "Field as _NebiusField" if field_collision else "Field"
    enum_import = "Enum as _NebiusEnum" if enum_collision else "Enum"
    enum_base = "_NebiusEnum" if enum_collision else "Enum"
    lines = [
        "# Generated by nebius_generator. DO NOT EDIT!",
        '"""Direct protobuf classes for this package."""',
        "",
        "from __future__ import annotations",
        "",
        "from builtins import (",
        "    bool as _NebiusBool, bytes as _NebiusBytes, dict as _NebiusDict,",
        "    float as _NebiusFloat, int as _NebiusInt, object as _NebiusObject,",
        "    property as _NebiusProperty, str as _NebiusStr,",
        ")",
        "from collections.abc import (",
        "    AsyncIterable as _NebiusAsyncIterable, Iterable as _NebiusIterable,",
        "    Mapping as _NebiusMapping, MutableMapping as _NebiusMutableMapping,",
        "    MutableSequence as _NebiusMutableSequence,",
        ")",
        "from datetime import datetime as _NebiusDatetime, "
        "timedelta as _NebiusTimedelta",
        "from logging import getLogger as _nebius_get_logger",
        "from typing import (",
        "    TYPE_CHECKING as _NEBIUS_TYPE_CHECKING, ClassVar as _NebiusClassVar,",
        "    Literal as _NebiusLiteral, TypeAlias as _NebiusTypeAlias, "
        "cast as _nebius_cast,",
        ")",
        "from typing_extensions import Unpack as _NebiusUnpack",
        "",
        f"from {runtime}.aio.client import Client as _NebiusClient, "
        "ClientWithOperations as _NebiusClientWithOperations",
        f"from {runtime}.aio.operation import Operation as _NebiusOperation",
        f"from {runtime}.aio.request import Request as _NebiusRequest",
        f"from {runtime}.aio.request_kwargs import "
        "RequestKwargs as _NebiusRequestKwargs, "
        "StreamRequestKwargs as _NebiusStreamRequestKwargs",
        f"from {runtime}.aio.stream import StreamRequest as _NebiusStreamRequest",
        f"from {runtime}.base.protos.codec import (",
        "    BOOL, BYTES, DOUBLE, FIXED32, FIXED64, FLOAT, INT32, INT64,",
        "    SFIXED32, SFIXED64, SINT32, SINT64, STRING, UINT32, UINT64, enum_codec,",
        ")",
        f"from {runtime}.base.protos.direct import (",
        f"    {field_import}, Message, OneOf as _NebiusOneOf,",
        "    OneOfMatchError as _NebiusOneOfMatchError,",
        "    SerializableMessage as _NebiusSerializableMessage, message_codec,",
        ")",
        f"from {runtime}.base.fieldmask_protobuf import ensure_reset_mask_in_metadata",
        f"from {runtime}.base.protos.pb_enum import {enum_import}",
        f"from {runtime}.base.protos.extensions import Extension as _NebiusExtension",
        f"from {runtime}.base.protos.unset import Unset as _NEBIUS_UNSET, "
        "UnsetType as _NebiusUnsetType",
        f"from {runtime}.aio.request_status import "
        "RequestStatus as _NebiusRequestStatus",
        f"from {runtime}.base.protos.well_known_direct import (",
        "    datetime_to_timestamp as _nebius_datetime_to_timestamp,",
        "    duration_to_timedelta as _nebius_duration_to_timedelta,",
        "    request_status_to_status as _nebius_request_status_to_status,",
        "    status_to_request_status as _nebius_status_to_request_status,",
        "    timedelta_to_duration as _nebius_timedelta_to_duration,",
        "    timestamp_to_datetime as _nebius_timestamp_to_datetime,",
        ")",
        f"from {registry_import} import EXTENSION_HANDLES, EXTENSIONS, REGISTRY",
        "",
        "# @@nebius-section:type_imports@@",
    ]
    lines.extend(_type_import_lines(package, messages, services, extensions, graph))
    lines.extend(
        [
            "# @@nebius-section:enums@@",
        ]
    )
    for enum in enums:
        implementation = enum.implementation_name
        enum_deprecation = graph.annotations.deprecation(enum.proto.options, "enum")
        enum_summary = (
            enum_deprecation.summary() if enum_deprecation is not None else ""
        )
        lines.append(f"class {implementation}({enum_base}):")
        _append_docstring(
            lines,
            "    ",
            _documentation(
                graph,
                enum.source_file,
                enum.source_path,
                deprecation_summary=enum_summary,
            ),
        )
        lines.extend(
            [
                f"    __PROTO_FULL_NAME__ = {enum.full_name!r}",
                "    __REGISTRY__ = REGISTRY",
                "    __PROTO_DESCRIPTOR__ = "
                f"REGISTRY.enum_descriptor({enum.full_name!r})",
                "    __PB2_DESCRIPTOR__ = __PROTO_DESCRIPTOR__",
            ]
        )
        for index, value in enumerate(enum.proto.value):
            value_name = graph.enum_value_python_name(enum, value)
            lines.append(f"    {value_name} = {value.number}")
            value_deprecation = graph.annotations.deprecation(
                value.options, "enum_value"
            )
            _append_docstring(
                lines,
                "    ",
                _documentation(
                    graph,
                    enum.source_file,
                    (*enum.source_path, 2, index),
                    deprecation_summary=(
                        value_deprecation.summary()
                        if value_deprecation is not None
                        else ""
                    ),
                ),
            )
        lines.append(f"{_named_alias(enum.full_name)} = {implementation}")
        lines.append("")
    lines.append("# @@nebius-section:messages@@")
    for message in messages:
        lines.extend(_message_source(message, graph))
        lines.append(
            f"{_named_alias(message.full_name)} = {message.implementation_name}"
        )
        lines.extend(["", ""])
    lines.append("# @@nebius-section:fields@@")
    for message in messages:
        constants: list[str] = []
        for field in message.proto.field:
            constant = _constant(message.full_name, field.name)
            runtime_field = "_NebiusField" if field_collision else "Field"
            lines.append(
                f"{constant} = "
                f"{_field_expression(message, field, graph, runtime_field)}"
            )
            constants.append(constant)
        tuple_text = ", ".join(constants)
        if len(constants) == 1:
            tuple_text += ","
        lines.append(f"{message.implementation_name}.__FIELDS__ = ({tuple_text})")
        lines.append("")
    lines.append("# @@nebius-section:attachments@@")
    for enum in enums:
        if "." in enum.python_qualname:
            _, _, child = enum.python_qualname.rpartition(".")
            implementation = enum.implementation_name
            lines.append(f"{implementation}.__name__ = {child!r}")
            lines.append(f"{implementation}.__qualname__ = {enum.python_qualname!r}")
    for message in messages:
        if "." in message.python_qualname:
            _, _, child = message.python_qualname.rpartition(".")
            lines.append(f"{message.implementation_name}.__name__ = {child!r}")
            lines.append(
                f"{message.implementation_name}.__qualname__ = "
                f"{message.python_qualname!r}"
            )
    lines.append("# @@nebius-section:extensions@@")
    for extension in extensions:
        extension_name = extension.python_name
        extension_type = _extension_type(extension.proto, package, graph)
        target = (
            graph.messages[extension.scope].implementation_name + "."
            if extension.scope is not None
            else ""
        )
        annotation = f"_NebiusExtension[{extension_type}]"
        lines.append(
            f"{target}{extension_name}"
            + ("" if extension.scope is not None else f": {annotation}")
            + f" = _nebius_cast({annotation!r}, "
            + f"EXTENSION_HANDLES[{extension.full_name!r}])"
        )
    if extensions:
        lines.append("")
    lines.append("# @@nebius-section:services@@")
    for service in services:
        client_name = service.python_name + "Client"
        endpoint_name = graph.annotations.api_service_name(service.proto.options)
        service_deprecation = graph.annotations.deprecation(
            service.proto.options, "service"
        )
        service_summary = (
            service_deprecation.summary() if service_deprecation is not None else ""
        )
        operation_method = next(
            (
                method
                for method in service.proto.method
                if method.output_type.lstrip(".") in _OPERATION_SERVICES
                and service.full_name
                != _OPERATION_SERVICES[method.output_type.lstrip(".")]
            ),
            None,
        )
        if operation_method is None:
            client_base = "_NebiusClient"
        else:
            operation_name = operation_method.output_type.lstrip(".")
            operation_type = _named_type(operation_name, package, graph)
            operation_service = _service_type(
                _OPERATION_SERVICES[operation_name], package, graph
            )
            client_base = (
                f"_NebiusClientWithOperations[{operation_type}, {operation_service}]"
            )
        lines.append(f"class {client_name}({client_base}):")
        _append_docstring(
            lines,
            "    ",
            _documentation(
                graph,
                service.source_file,
                service.source_path,
                deprecation_summary=service_summary,
                additional=(
                    f"This class provides client methods for the "
                    f"``{service.full_name}`` service."
                ),
            ),
        )
        lines.extend(
            [
                f"    __service_name__ = {service.full_name!r}",
                f"    __api_service_name__ = {endpoint_name!r}",
                "    __registry__ = REGISTRY",
                "",
                "    @classmethod",
                "    def get_descriptor(cls) -> _NebiusObject:",
                f"        return REGISTRY.service_descriptor({service.full_name!r})",
                "",
                "    __PB2_DESCRIPTOR__ = "
                f"REGISTRY.service_descriptor({service.full_name!r})",
            ]
        )
        if service_deprecation is not None:
            lines.append(f"    __service_deprecation_details__ = {service_summary!r}")
        if operation_method is not None:
            operation_name = operation_method.output_type.lstrip(".")
            operation_service = _service_type(
                _OPERATION_SERVICES[operation_name], package, graph
            )
            lines.extend(
                [
                    "    __operation_type__ = "
                    f"{_named_type(operation_name, package, graph)}",
                    f"    __operation_service_class__ = {operation_service}",
                    f"    __operation_source_method__ = {operation_method.name!r}",
                ]
            )
        for method_index, method in enumerate(service.proto.method):
            method_name = graph.method_python_name(service, method)
            input_type = _named_type(method.input_type, package, graph)
            output_type = _named_type(method.output_type, package, graph)
            output_name = method.output_type.lstrip(".")
            annotated_updater = graph.annotations.method_is_updater(method.options)
            updater = (
                method.name == "Update"
                if annotated_updater is None
                else annotated_updater
            )
            request_annotation = (
                f"_NebiusAsyncIterable[{input_type}] | "
                f"_NebiusIterable[{input_type}] | None"
                if method.client_streaming
                else input_type
            )
            request_argument = (
                f"request: {request_annotation} = None"
                if method.client_streaming
                else f"request: {request_annotation}"
            )
            operation_output = output_name in _OPERATION_SERVICES
            response_type = (
                f"_NebiusOperation[{output_type}]" if operation_output else output_type
            )
            result_annotation = (
                f"_NebiusStreamRequest[{input_type}, {output_type}]"
                if method.client_streaming or method.server_streaming
                else f"_NebiusRequest[{input_type}, {response_type}]"
            )
            kwargs_type = (
                "_NebiusStreamRequestKwargs"
                if method.client_streaming or method.server_streaming
                else "_NebiusRequestKwargs"
            )
            lines.extend(
                [
                    "",
                    f"    def {method_name}(",
                    "        self,",
                    f"        {request_argument},",
                    f"        **kwargs: _NebiusUnpack[{kwargs_type}],",
                    f"    ) -> {result_annotation}:",
                ]
            )
            method_deprecation = graph.annotations.deprecation(method.options, "method")
            method_summary = (
                method_deprecation.summary() if method_deprecation is not None else ""
            )
            _append_docstring(
                lines,
                "        ",
                _documentation(
                    graph,
                    service.source_file,
                    (*service.source_path, 2, method_index),
                    deprecation_summary=method_summary,
                    additional=(
                        "The request object is returned without starting the RPC."
                    ),
                ),
            )
            if method_deprecation is not None:
                lines.append(
                    _warning(
                        "Method",
                        f"{service.full_name}.{method.name}",
                        method_summary,
                        "        ",
                    )
                )
            if updater and not method.client_streaming:
                lines.append(
                    "        kwargs['metadata'] = ensure_reset_mask_in_metadata("
                )
                lines.append("            request, kwargs.get('metadata'),")
                lines.append("        )")
            if method.client_streaming or method.server_streaming:
                lines.extend(
                    [
                        "        return super().stream_request(",
                        f"            method={method.name!r},",
                        "            request=request,",
                        "            result_class=_nebius_cast("
                        f"'type[{output_type}]', "
                        f"REGISTRY.message_class({output_name!r}),"
                        "            ),",
                        f"            client_streaming={method.client_streaming!r},",
                        f"            server_streaming={method.server_streaming!r},",
                        "            **kwargs,",
                        "        )",
                    ]
                )
                continue
            lines.extend(
                [
                    "        return super().request(",
                    f"            method={method.name!r},",
                    "            request=request,",
                    "            result_pb2_class="
                    f"REGISTRY.message_class({output_name!r}),",
                ]
            )
            if operation_output:
                lines.append("            result_wrapper=_NebiusOperation,")
            lines.extend(["            **kwargs,", "        )"])
        lines.extend(["", ""])
    exported = [
        item.python_qualname for item in enums if "." not in item.python_qualname
    ]
    exported.extend(
        item.python_qualname for item in messages if "." not in item.python_qualname
    )
    exported.extend(item.python_name for item in extensions if item.scope is None)
    exported.extend(item.python_name + "Client" for item in services)
    lines.append("# @@nebius-section:exports@@")
    lines.append(f"__all__ = {sorted(exported)!r}")
    lines.append("")
    return "\n".join(lines)


def package_source_files(package: str, graph: Graph) -> tuple[str, ...]:
    """Return source files contributing declarations to one output package."""
    return tuple(
        sorted(
            {
                *[
                    item.source_file
                    for item in graph.messages.values()
                    if item.package == package and not item.map_entry
                ],
                *[
                    item.source_file
                    for item in graph.enums.values()
                    if item.package == package
                ],
                *[
                    item.source_file
                    for item in graph.services.values()
                    if item.package == package
                ],
                *[
                    item.source_file
                    for item in graph.extensions.values()
                    if item.package == package
                ],
            }
        )
    )


def emit_package_fragment(package: str, source_file: str, graph: Graph) -> str:
    """Analyze declarations owned by one source file into mergeable Python IR."""
    if source_file not in package_source_files(package, graph):
        raise GeneratorError(
            f"source file {source_file!r} does not contribute to {package!r}"
        )
    return _package_source(package, graph, frozenset({source_file}))


def _split_package_fragment(source: str) -> tuple[str, dict[str, str]]:
    marker_prefix = "# @@nebius-section:"
    header: list[str] = []
    sections: dict[str, list[str]] = {name: [] for name in _PACKAGE_SECTIONS}
    current: str | None = None
    for line in source.splitlines():
        if line.startswith(marker_prefix) and line.endswith("@@"):
            current = line.removeprefix(marker_prefix).removesuffix("@@")
            if current not in sections:
                raise GeneratorError(f"unknown package IR section {current!r}")
            continue
        (header if current is None else sections[current]).append(line)
    if current is None:
        raise GeneratorError("package IR contains no sections")
    return "\n".join(header), {
        name: "\n".join(lines).strip("\n") for name, lines in sections.items()
    }


def _package_models(package: str, source_files: frozenset[str], graph: Graph) -> tuple[
    tuple[MessageModel, ...],
    tuple[ServiceModel, ...],
    tuple[ExtensionModel, ...],
]:
    messages = tuple(
        item
        for item in graph.messages.values()
        if item.package == package
        and not item.map_entry
        and item.source_file in source_files
    )
    services = tuple(
        item
        for item in graph.services.values()
        if item.package == package and item.source_file in source_files
    )
    extensions = tuple(
        item
        for item in graph.extensions.values()
        if item.package == package and item.source_file in source_files
    )
    return messages, services, extensions


def _same_package_import_lines(
    package: str,
    source_files: frozenset[str],
    messages: tuple[MessageModel, ...],
    services: tuple[ServiceModel, ...],
    extensions: tuple[ExtensionModel, ...],
    graph: Graph,
) -> list[str]:
    referenced_names: set[str] = set()
    for message in messages:
        for field in message.proto.field:
            fields = _map_fields(field, graph) or (field,)
            referenced_names.update(
                item.type_name.lstrip(".")
                for item in fields
                if item.type
                in {
                    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
                    descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
                }
            )
    for service in services:
        for method in service.proto.method:
            referenced_names.update(
                (method.input_type.lstrip("."), method.output_type.lstrip("."))
            )
    for extension in extensions:
        if extension.proto.type in {
            descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
            descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        }:
            referenced_names.add(extension.proto.type_name.lstrip("."))

    typing_names: set[str] = set()
    for full_name in referenced_names:
        target = graph.messages.get(full_name) or graph.enums.get(full_name)
        if (
            target is None
            or target.package != package
            or target.source_file in source_files
        ):
            continue
        typing_names.add(_named_alias(target.full_name))

    runtime_names: set[str] = set()
    for service in services:
        for method in service.proto.method:
            operation_name = method.output_type.lstrip(".")
            operation_service_name = _OPERATION_SERVICES.get(operation_name)
            if operation_service_name is None:
                continue
            operation = graph.messages[operation_name]
            operation_service = graph.services[operation_service_name]
            if (
                operation.package == package
                and operation.source_file not in source_files
            ):
                runtime_names.add(_named_alias(operation.full_name))
            if (
                operation_service.package == package
                and operation_service.source_file not in source_files
            ):
                runtime_names.add(operation_service.python_name + "Client")
    typing_names.difference_update(runtime_names)

    lines: list[str] = []
    if runtime_names:
        lines.append("from . import (")
        lines.extend(f"    {name} as {name}," for name in sorted(runtime_names))
        lines.extend((")", ""))
    if typing_names:
        lines.append("if _NEBIUS_TYPE_CHECKING:")
        lines.append("    from . import (")
        lines.extend(f"        {name} as {name}," for name in sorted(typing_names))
        lines.extend(("    )", ""))
    return lines


def _linked_package_source(
    package: str,
    header: str,
    parsed: list[tuple[str, dict[str, str]]],
    graph: Graph,
) -> tuple[str, tuple[str, ...]]:
    source_files = frozenset(source_file for source_file, _ in parsed)
    messages, services, extensions = _package_models(package, source_files, graph)
    lines = [header.rstrip(), ""]
    for section in _PACKAGE_SECTIONS[:-1]:
        lines.append(f"# @@nebius-section:{section}@@")
        if section == "type_imports":
            type_imports = _type_import_lines(
                package,
                messages,
                services,
                extensions,
                graph,
            )
            type_imports.extend(
                _same_package_import_lines(
                    package,
                    source_files,
                    messages,
                    services,
                    extensions,
                    graph,
                )
            )
            if type_imports:
                lines.extend(("\n".join(type_imports).rstrip(), ""))
            continue
        for _, sections in parsed:
            if sections[section]:
                lines.extend((sections[section], ""))
    exported: set[str] = set()
    for _, sections in parsed:
        assignment = sections["exports"].strip()
        prefix = "__all__ = "
        if not assignment.startswith(prefix):
            raise GeneratorError("invalid exports package IR")
        exported.update(ast.literal_eval(assignment.removeprefix(prefix)))
    lines.extend(
        (
            "# @@nebius-section:exports@@",
            f"__all__ = {sorted(exported)!r}",
            "",
        )
    )
    return "\n".join(lines), tuple(sorted(exported))


def _shard_defined_names(
    package: str, source_files: frozenset[str], graph: Graph
) -> tuple[str, ...]:
    names = {
        item.implementation_name
        for item in graph.messages.values()
        if item.package == package
        and not item.map_entry
        and item.source_file in source_files
    }
    names.update(
        _named_alias(item.full_name)
        for item in graph.messages.values()
        if item.package == package
        and not item.map_entry
        and item.source_file in source_files
    )
    names.update(
        item.implementation_name
        for item in graph.enums.values()
        if item.package == package and item.source_file in source_files
    )
    names.update(
        _named_alias(item.full_name)
        for item in graph.enums.values()
        if item.package == package and item.source_file in source_files
    )
    names.update(
        item.python_name + "Client"
        for item in graph.services.values()
        if item.package == package and item.source_file in source_files
    )
    names.update(
        item.python_name
        for item in graph.extensions.values()
        if item.package == package
        and item.scope is None
        and item.source_file in source_files
    )
    return tuple(sorted(names))


def _lazy_package_source(
    shards: list[tuple[str, tuple[str, ...], tuple[str, ...]]],
    registry_import: str,
) -> str:
    name_to_shard = {name: shard for shard, defined, _ in shards for name in defined}
    public_exports = sorted({name for _, _, exported in shards for name in exported})
    defined_by_shard = {shard: defined for shard, defined, _ in shards}
    lines = [
        "# Generated by nebius_generator. DO NOT EDIT!",
        '"""Lazy public exports for a sharded direct protobuf package."""',
        "",
        "from __future__ import annotations",
        "",
        "from builtins import AttributeError as _NebiusAttributeError",
        "from builtins import getattr as _NebiusGetattr",
        "from builtins import globals as _NebiusGlobals",
        "from builtins import isinstance as _NebiusIsinstance",
        "from builtins import sorted as _NebiusSorted",
        "from builtins import type as _NebiusType",
        "from importlib import import_module as _nebius_import_module",
        "from typing import TYPE_CHECKING as _NEBIUS_TYPE_CHECKING",
        "",
        f"_NEBIUS_EXPORT_SHARDS = {name_to_shard!r}",
        f"_NEBIUS_SHARD_NAMES = {defined_by_shard!r}",
        "",
        "if _NEBIUS_TYPE_CHECKING:",
        f"    from {registry_import} import (",
        "        EXTENSIONS as EXTENSIONS,",
        "        EXTENSION_HANDLES as EXTENSION_HANDLES,",
        "        REGISTRY as REGISTRY,",
        "    )",
    ]
    for shard, defined, _ in shards:
        type_visible = tuple(
            name
            for name in defined
            if name not in {"EXTENSIONS", "EXTENSION_HANDLES", "REGISTRY"}
        )
        if not type_visible:
            continue
        lines.append(f"    from .{shard} import (")
        lines.extend(f"        {name} as {name}," for name in type_visible)
        lines.append("    )")
    lines.extend(
        [
            "",
            "else:",
            "    def _nebius_module_getattr(name: str) -> object:",
            "        shard = _NEBIUS_EXPORT_SHARDS.get(name)",
            "        if shard is None:",
            "            raise _NebiusAttributeError(",
            "                f'module {__name__!r} has no attribute {name!r}'",
            "            )",
            "        module = _nebius_import_module(f'{__name__}.{shard}')",
            "        for exported_name in _NEBIUS_SHARD_NAMES[shard]:",
            "            value = _NebiusGetattr(module, exported_name)",
            "            if _NebiusIsinstance(value, _NebiusType):",
            "                value.__module__ = __name__",
            "            _NebiusGlobals()[exported_name] = value",
            "        return _NebiusGlobals()[name]",
            "",
            "    def _nebius_module_dir() -> list[str]:",
            "        return _NebiusSorted({*_NebiusGlobals(), *_NEBIUS_EXPORT_SHARDS})",
            "",
            "    _NebiusGlobals()['__getattr__'] = _nebius_module_getattr",
            "    _NebiusGlobals()['__dir__'] = _nebius_module_dir",
            "",
            f"__all__ = {public_exports!r}",
            "",
        ]
    )
    return "\n".join(lines)


def link_package_fragments(
    package: str, fragments: Iterable[tuple[str, str]], graph: Graph
) -> tuple[GeneratedFile, ...]:
    """Merge source-file IR into one module or deterministic lazy shards."""
    ordered = sorted(fragments)
    if not ordered:
        raise GeneratorError(f"package has no fragments: {package!r}")
    headers: set[str] = set()
    parsed: list[tuple[str, dict[str, str]]] = []
    for source_file, source in ordered:
        header, sections = _split_package_fragment(source)
        headers.add(header)
        parsed.append((source_file, sections))
    if len(headers) != 1:
        raise GeneratorError(f"package fragment headers differ: {package!r}")
    header = headers.pop()
    output_package = graph.output_package(package)
    output_directory = output_package.replace(".", "/")
    batches: list[list[tuple[str, dict[str, str]]]] = []
    current: list[tuple[str, dict[str, str]]] = []
    current_lines = 0
    for fragment in parsed:
        fragment_lines = sum(len(value.splitlines()) for value in fragment[1].values())
        if current and current_lines + fragment_lines > _SHARD_LINE_LIMIT:
            batches.append(current)
            current = []
            current_lines = 0
        current.append(fragment)
        current_lines += fragment_lines
    if current:
        batches.append(current)

    generated: list[GeneratedFile] = []
    shard_metadata: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for index, batch in enumerate(batches):
        shard = f"_impl_{index:03d}"
        shard_source, exported = _linked_package_source(package, header, batch, graph)
        source_files = frozenset(source_file for source_file, _ in batch)
        defined = _shard_defined_names(package, source_files, graph)
        if index == 0:
            defined = tuple(
                sorted({*defined, "EXTENSIONS", "EXTENSION_HANDLES", "REGISTRY"})
            )
        generated.append(
            GeneratedFile(
                name=f"{output_directory}/{shard}.py",
                content=shard_source,
            )
        )
        shard_metadata.append((shard, defined, exported))
    return (
        GeneratedFile(
            name=output_directory + "/__init__.py",
            content=_lazy_package_source(
                shard_metadata,
                _relative_registry(output_package, graph.options.package_prefix),
            ),
        ),
        *generated,
    )


def registry_packages(graph: Graph) -> tuple[str, ...]:
    """Return stable package owners for registry metadata fragments."""
    return packages(graph)


def _registry_fragment_source(package: str | None, graph: Graph) -> str:
    runtime = graph.options.runtime_package
    public_packages = frozenset(packages(graph))
    package_files = (
        (file for file in graph.files.values() if file.package == package)
        if package is not None
        else (
            file for file in graph.files.values() if file.package not in public_packages
        )
    )
    serialized = tuple(
        serialize_file_descriptor(proto)
        for proto in sorted(package_files, key=lambda item: item.name)
    )
    lines = [
        "# Generated by nebius_generator. DO NOT EDIT!",
        '"""Package-owned inputs for the namespace registry."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any as _NebiusAny",
        "",
        f"from {runtime}.base.protos.extensions import (",
        "    Extension, ExtensionRegistry,",
        ")",
        f"from {runtime}.base.protos.registry import (",
        "    MessageReference, Registry, RegistryFragment,",
        ")",
        "",
    ]
    package_extensions = sorted(
        (
            item
            for item in graph.extensions.values()
            if package is not None and item.package == package
        ),
        key=lambda item: item.full_name,
    )
    if package_extensions:
        lines.extend(
            [
                f"from {runtime}.base.protos.direct import message_codec",
                f"from {runtime}.base.protos.codec import (",
                "    BOOL, BYTES, DOUBLE, FIXED32, FIXED64, FLOAT, INT32, INT64,",
                "    SFIXED32, SFIXED64, SINT32, SINT64, STRING, UINT32, UINT64,",
                "    enum_codec,",
                ")",
                "",
            ]
        )
    lines.append("EXTENDEES: tuple[tuple[str, tuple[tuple[int, int], ...]], ...] = (")
    for message in sorted(
        (
            item
            for item in graph.messages.values()
            if package is not None and item.package == package
        ),
        key=lambda item: item.full_name,
    ):
        ranges = tuple((item.start, item.end) for item in message.proto.extension_range)
        if ranges:
            lines.append(f"    ({message.full_name!r}, {ranges!r}),")
    lines.extend([")", "", "_SYMBOLS: dict[str, MessageReference] = {"])
    for message in sorted(
        (
            item
            for item in graph.messages.values()
            if package is not None and item.package == package
        ),
        key=lambda item: item.full_name,
    ):
        if message.map_entry:
            continue
        symbol = f"    {message.full_name!r}: MessageReference("
        lines.append(
            symbol
            + "module=__package__, "
            + f"qualname={message.implementation_name!r}),"
        )
    lines.append("}")
    lines.extend(["", "_ENUM_SYMBOLS: dict[str, MessageReference] = {"])
    for enum in sorted(
        (
            item
            for item in graph.enums.values()
            if package is not None and item.package == package
        ),
        key=lambda item: item.full_name,
    ):
        symbol = f"    {enum.full_name!r}: MessageReference("
        lines.append(
            symbol + "module=__package__, " + f"qualname={enum.implementation_name!r}),"
        )
    lines.append("}")
    lines.extend(
        [
            "",
            "FRAGMENT = RegistryFragment(",
            "    symbols=_SYMBOLS,",
            "    enum_symbols=_ENUM_SYMBOLS,",
            f"    serialized_files={serialized!r},",
            ")",
            "",
        ]
    )
    lines.extend(
        [
            "def register_extensions(",
            "    REGISTRY: Registry,",
            "    EXTENSIONS: ExtensionRegistry,",
            "    EXTENSION_HANDLES: dict[str, Extension[_NebiusAny]],",
            ") -> None:",
        ]
    )
    if not package_extensions:
        lines.append("    pass")
    for index, extension in enumerate(package_extensions):
        codec_name = f"_EXTENSION_CODEC_{index}"
        lines.append(f"    {codec_name} = {_codec(extension.proto, graph)}")
        repeated = (
            extension.proto.label == descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
        )
        packable = extension.proto.type not in {
            descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
            descriptor_pb2.FieldDescriptorProto.TYPE_BYTES,
            descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        }
        packed = repeated and packable and extension.proto.options.packed
        lines.extend(
            [
                f"    _extension_{index} = Extension(",
                "        registry=EXTENSIONS,",
                f"        full_name={extension.full_name!r},",
                f"        extendee={extension.proto.extendee.lstrip('.')!r},",
                f"        number={extension.proto.number},",
                f"        value_codec={codec_name},",
                "        default_factory="
                + (
                    f"lambda: {codec_name}.normalize("
                    f"{_literal(_default(extension.proto, graph))}),"
                    if extension.proto.HasField("default_value")
                    else f"{codec_name}.default,"
                ),
                f"        repeated={repeated!r},",
                f"        packed={packed!r},",
                "        public=True,",
                "    )",
                f"    EXTENSIONS.register(_extension_{index})",
                f"    EXTENSION_HANDLES[{extension.full_name!r}] = _extension_{index}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def _registry_source(graph: Graph) -> str:
    runtime = graph.options.runtime_package
    fragment_packages = registry_packages(graph)
    lines = [
        "# Generated by nebius_generator. DO NOT EDIT!",
        '"""Namespace-owned registry composed from package fragments."""',
        "",
        "from typing import Any as _NebiusAny",
        "",
        f"from {runtime}.base.protos.extensions import Extension, ExtensionRegistry",
        f"from {runtime}.base.protos.registry import Registry",
        "",
    ]
    has_root_fragment = any(
        file.package not in fragment_packages for file in graph.files.values()
    )
    fragment_imports: list[str] = []
    if has_root_fragment:
        lines.append("from . import _registry_fragment as _fragment_root")
        fragment_imports.append("_fragment_root")
    for index, package in enumerate(fragment_packages):
        suffix = package or "_unpackaged"
        lines.append(
            f"from .{suffix} import _registry_fragment as _fragment_{index:03d}"
        )
        fragment_imports.append(f"_fragment_{index:03d}")
    lines.extend(
        [
            "",
            "REGISTRY = Registry.from_fragments((",
            *(f"    {name}.FRAGMENT," for name in fragment_imports),
            "))",
            "EXTENSIONS = ExtensionRegistry()",
            "EXTENSION_HANDLES: dict[str, Extension[_NebiusAny]] = {}",
            "",
        ]
    )
    for name in fragment_imports:
        lines.append(f"for _full_name, _ranges in {name}.EXTENDEES:")
        lines.append("    EXTENSIONS.add_extendee(_full_name, _ranges)")
    lines.append("")
    for name in fragment_imports:
        lines.append(
            f"{name}.register_extensions(" "REGISTRY, EXTENSIONS, EXTENSION_HANDLES)"
        )
    lines.extend(["EXTENSIONS.freeze()", ""])
    return "\n".join(lines)


def packages(graph: Graph) -> tuple[str, ...]:
    """Return proto packages that own generated public modules."""
    return tuple(
        sorted(
            {
                *[
                    item.package
                    for item in graph.messages.values()
                    if not item.map_entry
                ],
                *[item.package for item in graph.enums.values()],
                *[item.package for item in graph.services.values()],
                *[item.package for item in graph.extensions.values()],
            }
        )
    )


def emit_registry(graph: Graph) -> GeneratedFile:
    """Emit the namespace registry after the complete graph is linked."""
    return GeneratedFile(
        name=graph.options.package_prefix.replace(".", "/") + "/_registry.py",
        content=_registry_source(graph),
    )


def emit_registry_fragments(graph: Graph) -> tuple[GeneratedFile, ...]:
    """Emit package-local inputs consumed by the namespace registry."""
    generated: list[GeneratedFile] = []
    public_packages = frozenset(registry_packages(graph))
    if any(file.package not in public_packages for file in graph.files.values()):
        generated.append(
            GeneratedFile(
                name=(
                    graph.options.package_prefix.replace(".", "/")
                    + "/_registry_fragment.py"
                ),
                content=_registry_fragment_source(None, graph),
            )
        )
    for package in registry_packages(graph):
        output_directory = graph.output_package(package).replace(".", "/")
        generated.append(
            GeneratedFile(
                name=output_directory + "/_registry_fragment.py",
                content=_registry_fragment_source(package, graph),
            )
        )
    return tuple(generated)


def emit_package(package: str, graph: Graph) -> tuple[GeneratedFile, ...]:
    """Link one declared proto package into its canonical Python module."""
    if package not in packages(graph):
        raise GeneratorError(f"package has no generated declarations: {package!r}")
    return link_package_fragments(
        package,
        (
            (source_file, emit_package_fragment(package, source_file, graph))
            for source_file in package_source_files(package, graph)
        ),
        graph,
    )


def iter_emit(graph: Graph) -> Iterable[GeneratedFile]:
    """Yield the canonical tree without retaining all generated source in memory."""
    yield emit_registry(graph)
    yield from emit_registry_fragments(graph)
    for package in packages(graph):
        yield from emit_package(package, graph)


def emit(graph: Graph) -> list[GeneratedFile]:
    """Emit a normal plugin response in canonical linker order."""
    return list(iter_emit(graph))
