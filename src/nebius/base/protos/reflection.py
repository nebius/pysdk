"""Registry-owned protobuf descriptor facades built from raw descriptor protos."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from threading import RLock
from types import MappingProxyType
from typing import Any, Generic, TypeVar

from google.protobuf import descriptor_pb2, descriptor_pool

P = TypeVar("P")
OptionDecoder = Callable[[str, bytes], object]


def _camelcase(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _c_unescape_bytes(text: str) -> bytes:
    """Decode the C escapes used by bytes defaults in descriptor protos."""
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
        character = text[index]
        if character != "\\":
            result.extend(character.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index == len(text):
            raise ValueError("unterminated C escape in bytes default")
        escaped = text[index]
        index += 1
        if escaped in escapes:
            result.append(escapes[escaped])
            continue
        if escaped in "01234567":
            digits = escaped
            while index < len(text) and len(digits) < 3 and text[index] in "01234567":
                digits += text[index]
                index += 1
            result.append(int(digits, 8) & 0xFF)
            continue
        if escaped == "x":
            start = index
            while index < len(text) and text[index] in "0123456789abcdefABCDEF":
                index += 1
            if index == start:
                raise ValueError("hex escape requires at least one digit")
            value = int(text[start:index], 16)
            if value > 0xFF:
                raise ValueError("hex escape exceeds 8 bits")
            result.append(value)
            continue
        raise ValueError(f"unknown C escape: \\{escaped}")
    return bytes(result)


def _parse_integer_default(text: str) -> int:
    sign = -1 if text.startswith("-") else 1
    unsigned = text[1:] if text[:1] in {"-", "+"} else text
    if unsigned.lower().startswith("0x"):
        return sign * int(unsigned[2:], 16)
    if len(unsigned) > 1 and unsigned.startswith("0"):
        return sign * int(unsigned, 8)
    return sign * int(unsigned, 10)


_CPP_TYPES = {
    descriptor_pb2.FieldDescriptorProto.TYPE_INT32: 1,
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT32: 1,
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32: 1,
    descriptor_pb2.FieldDescriptorProto.TYPE_INT64: 2,
    descriptor_pb2.FieldDescriptorProto.TYPE_SINT64: 2,
    descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64: 2,
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT32: 3,
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32: 3,
    descriptor_pb2.FieldDescriptorProto.TYPE_UINT64: 4,
    descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64: 4,
    descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE: 5,
    descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT: 6,
    descriptor_pb2.FieldDescriptorProto.TYPE_BOOL: 7,
    descriptor_pb2.FieldDescriptorProto.TYPE_ENUM: 8,
    descriptor_pb2.FieldDescriptorProto.TYPE_STRING: 9,
    descriptor_pb2.FieldDescriptorProto.TYPE_BYTES: 9,
    descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE: 10,
    descriptor_pb2.FieldDescriptorProto.TYPE_GROUP: 10,
}


class _Facade(Generic[P]):
    def __init__(
        self,
        owner: "Reflection",
        proto: P,
        *,
        name: str,
        full_name: str,
        file: "FileDescriptor",
        option_kind: str,
    ) -> None:
        self._owner = owner
        self._proto = proto
        self.name = name
        self.full_name = full_name
        self.file = file
        self._option_kind = option_kind
        self._options: object | None = None
        self.has_options = bool(getattr(proto, "options").SerializeToString())

    def GetOptions(self) -> object:  # noqa: N802
        """Decode localized direct options without exposing provider identity."""
        if self._options is None:
            options = getattr(self._proto, "options")
            self._options = self._owner.decode_options(
                self._option_kind, options.SerializeToString(deterministic=True)
            )
        return self._options

    def CopyToProto(self, target: Any) -> None:  # noqa: N802
        target.CopyFrom(self._proto)

    @property
    def provider_descriptor(self) -> Any:
        """Return the explicit private-provider interoperability boundary."""
        return self._owner.provider(self)


class FileDescriptor(_Facade[descriptor_pb2.FileDescriptorProto]):
    def __init__(self, owner: "Reflection", proto: descriptor_pb2.FileDescriptorProto):
        self.package = proto.package
        self.syntax = proto.syntax or "proto2"
        self.serialized_pb = proto.SerializeToString(deterministic=True)
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=proto.name,
            file=self,
            option_kind="google.protobuf.FileOptions",
        )
        self.dependencies: tuple[FileDescriptor, ...] = ()
        self.public_dependencies: tuple[FileDescriptor, ...] = ()
        self.message_types_by_name: Mapping[str, MessageDescriptor] = MappingProxyType(
            {}
        )
        self.enum_types_by_name: Mapping[str, EnumDescriptor] = MappingProxyType({})
        self.services_by_name: Mapping[str, ServiceDescriptor] = MappingProxyType({})
        self.extensions_by_name: Mapping[str, FieldDescriptor] = MappingProxyType({})


class MessageDescriptor(_Facade[descriptor_pb2.DescriptorProto]):
    def __init__(
        self,
        owner: "Reflection",
        proto: descriptor_pb2.DescriptorProto,
        *,
        full_name: str,
        file: FileDescriptor,
        containing_type: "MessageDescriptor | None",
    ) -> None:
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=full_name,
            file=file,
            option_kind="google.protobuf.MessageOptions",
        )
        self.containing_type = containing_type
        self.fields: tuple[FieldDescriptor, ...] = ()
        self.fields_by_name: Mapping[str, FieldDescriptor] = MappingProxyType({})
        self.fields_by_number: Mapping[int, FieldDescriptor] = MappingProxyType({})
        self.nested_types: tuple[MessageDescriptor, ...] = ()
        self.nested_types_by_name: Mapping[str, MessageDescriptor] = MappingProxyType(
            {}
        )
        self.enum_types: tuple[EnumDescriptor, ...] = ()
        self.enum_types_by_name: Mapping[str, EnumDescriptor] = MappingProxyType({})
        self.oneofs: tuple[OneofDescriptor, ...] = ()
        self.oneofs_by_name: Mapping[str, OneofDescriptor] = MappingProxyType({})
        self.extensions: tuple[FieldDescriptor, ...] = ()
        self.extensions_by_name: Mapping[str, FieldDescriptor] = MappingProxyType({})
        self.fields_by_camelcase_name: Mapping[str, FieldDescriptor] = MappingProxyType(
            {}
        )
        self.enum_values_by_name: Mapping[str, EnumValueDescriptor] = MappingProxyType(
            {}
        )
        self.extension_ranges = tuple(
            (item.start, item.end) for item in proto.extension_range
        )
        self.is_extendable = bool(self.extension_ranges)

    def EnumValueName(self, enum_name: str, number: int) -> str:  # noqa: N802
        return self.enum_types_by_name[enum_name].values_by_number[number].name


class EnumDescriptor(_Facade[descriptor_pb2.EnumDescriptorProto]):
    def __init__(
        self,
        owner: "Reflection",
        proto: descriptor_pb2.EnumDescriptorProto,
        *,
        full_name: str,
        file: FileDescriptor,
        containing_type: MessageDescriptor | None,
    ) -> None:
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=full_name,
            file=file,
            option_kind="google.protobuf.EnumOptions",
        )
        self.containing_type = containing_type
        self.is_closed = file.syntax == "proto2"
        self.values: tuple[EnumValueDescriptor, ...] = ()
        self.values_by_name: Mapping[str, EnumValueDescriptor] = MappingProxyType({})
        self.values_by_number: Mapping[int, EnumValueDescriptor] = MappingProxyType({})


class EnumValueDescriptor(_Facade[descriptor_pb2.EnumValueDescriptorProto]):
    def __init__(
        self,
        owner: "Reflection",
        proto: descriptor_pb2.EnumValueDescriptorProto,
        enum: EnumDescriptor,
        index: int,
    ):
        scope = (
            enum.containing_type.full_name
            if enum.containing_type is not None
            else enum.file.package
        )
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=f"{scope}.{proto.name}" if scope else proto.name,
            file=enum.file,
            option_kind="google.protobuf.EnumValueOptions",
        )
        self.type = enum
        self.number = proto.number
        self.index = index


class OneofDescriptor(_Facade[descriptor_pb2.OneofDescriptorProto]):
    def __init__(
        self,
        owner: "Reflection",
        proto: descriptor_pb2.OneofDescriptorProto,
        message: MessageDescriptor,
        index: int,
    ):
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=f"{message.full_name}.{proto.name}",
            file=message.file,
            option_kind="google.protobuf.OneofOptions",
        )
        self.containing_type = message
        self.index = index
        self.fields: tuple[FieldDescriptor, ...] = ()


class FieldDescriptor(_Facade[descriptor_pb2.FieldDescriptorProto]):
    LABEL_OPTIONAL = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    LABEL_REQUIRED = descriptor_pb2.FieldDescriptorProto.LABEL_REQUIRED
    LABEL_REPEATED = descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
    TYPE_DOUBLE = descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE
    TYPE_FLOAT = descriptor_pb2.FieldDescriptorProto.TYPE_FLOAT
    TYPE_INT64 = descriptor_pb2.FieldDescriptorProto.TYPE_INT64
    TYPE_UINT64 = descriptor_pb2.FieldDescriptorProto.TYPE_UINT64
    TYPE_INT32 = descriptor_pb2.FieldDescriptorProto.TYPE_INT32
    TYPE_FIXED64 = descriptor_pb2.FieldDescriptorProto.TYPE_FIXED64
    TYPE_FIXED32 = descriptor_pb2.FieldDescriptorProto.TYPE_FIXED32
    TYPE_BOOL = descriptor_pb2.FieldDescriptorProto.TYPE_BOOL
    TYPE_STRING = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
    TYPE_GROUP = descriptor_pb2.FieldDescriptorProto.TYPE_GROUP
    TYPE_MESSAGE = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
    TYPE_BYTES = descriptor_pb2.FieldDescriptorProto.TYPE_BYTES
    TYPE_UINT32 = descriptor_pb2.FieldDescriptorProto.TYPE_UINT32
    TYPE_ENUM = descriptor_pb2.FieldDescriptorProto.TYPE_ENUM
    TYPE_SFIXED32 = descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED32
    TYPE_SFIXED64 = descriptor_pb2.FieldDescriptorProto.TYPE_SFIXED64
    TYPE_SINT32 = descriptor_pb2.FieldDescriptorProto.TYPE_SINT32
    TYPE_SINT64 = descriptor_pb2.FieldDescriptorProto.TYPE_SINT64
    CPPTYPE_INT32 = 1
    CPPTYPE_INT64 = 2
    CPPTYPE_UINT32 = 3
    CPPTYPE_UINT64 = 4
    CPPTYPE_DOUBLE = 5
    CPPTYPE_FLOAT = 6
    CPPTYPE_BOOL = 7
    CPPTYPE_ENUM = 8
    CPPTYPE_STRING = 9
    CPPTYPE_BYTES = 9
    CPPTYPE_MESSAGE = 10

    def __init__(
        self,
        owner: "Reflection",
        proto: descriptor_pb2.FieldDescriptorProto,
        *,
        full_name: str,
        file: FileDescriptor,
        containing_type: MessageDescriptor | None,
        index: int,
        is_extension: bool = False,
    ):
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=full_name,
            file=file,
            option_kind="google.protobuf.FieldOptions",
        )
        self.number = proto.number
        self.index = index
        self.type = proto.type
        self.label = proto.label
        self.json_name = proto.json_name or _camelcase(proto.name)
        self.camelcase_name = _camelcase(proto.name)
        self.containing_type = containing_type
        self.is_extension = is_extension
        self.message_type: MessageDescriptor | None = None
        self.enum_type: EnumDescriptor | None = None
        self.containing_oneof: OneofDescriptor | None = None
        self.extension_scope: MessageDescriptor | None = None
        self.has_presence = False
        self.has_default_value = proto.HasField("default_value")
        self.default_value: Any = None
        self.is_repeated = proto.label == self.LABEL_REPEATED
        self.is_required = proto.label == self.LABEL_REQUIRED
        self.is_packed = False
        self.cpp_type = _CPP_TYPES[proto.type]


class ServiceDescriptor(_Facade[descriptor_pb2.ServiceDescriptorProto]):
    def __init__(
        self,
        owner: "Reflection",
        proto: descriptor_pb2.ServiceDescriptorProto,
        *,
        full_name: str,
        file: FileDescriptor,
        index: int,
    ):
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=full_name,
            file=file,
            option_kind="google.protobuf.ServiceOptions",
        )
        self.index = index
        self.methods: tuple[MethodDescriptor, ...] = ()
        self.methods_by_name: Mapping[str, MethodDescriptor] = MappingProxyType({})

    def FindMethodByName(self, name: str) -> "MethodDescriptor | None":  # noqa: N802
        return self.methods_by_name.get(name)


class MethodDescriptor(_Facade[descriptor_pb2.MethodDescriptorProto]):
    def __init__(
        self,
        owner: "Reflection",
        proto: descriptor_pb2.MethodDescriptorProto,
        service: ServiceDescriptor,
        index: int,
    ):
        super().__init__(
            owner,
            proto,
            name=proto.name,
            full_name=f"{service.full_name}.{proto.name}",
            file=service.file,
            option_kind="google.protobuf.MethodOptions",
        )
        self.containing_service = service
        self.index = index
        self.input_type: MessageDescriptor
        self.output_type: MessageDescriptor
        self.client_streaming = proto.client_streaming
        self.server_streaming = proto.server_streaming


class Reflection:
    """Immutable linked descriptor graph for one generated namespace."""

    def __init__(
        self, serialized_files: Sequence[bytes], decode_options: OptionDecoder
    ):
        self.decode_options = decode_options
        self._serialized_files = tuple(serialized_files)
        self._provider_pool: descriptor_pool.DescriptorPool | None = None
        self._provider_lock = RLock()
        protos = [
            descriptor_pb2.FileDescriptorProto.FromString(raw)
            for raw in serialized_files
        ]
        self.files_by_name: Mapping[str, FileDescriptor]
        self.messages_by_name: Mapping[str, MessageDescriptor]
        self.enums_by_name: Mapping[str, EnumDescriptor]
        self.services_by_name: Mapping[str, ServiceDescriptor]
        self.extensions_by_name: Mapping[str, FieldDescriptor]
        self._build(protos)

    @staticmethod
    def _qualified(prefix: str, name: str) -> str:
        return f"{prefix}.{name}" if prefix else name

    def _build(self, protos: Sequence[descriptor_pb2.FileDescriptorProto]) -> None:
        file_names = [proto.name for proto in protos]
        if len(file_names) != len(set(file_names)):
            raise ValueError("duplicate protobuf file name")
        files = {proto.name: FileDescriptor(self, proto) for proto in protos}
        messages: dict[str, MessageDescriptor] = {}
        enums: dict[str, EnumDescriptor] = {}
        services: dict[str, ServiceDescriptor] = {}
        extensions: dict[str, FieldDescriptor] = {}
        symbols: dict[str, str] = {}

        def claim(full_name: str, kind: str) -> None:
            previous = symbols.get(full_name)
            if previous is not None:
                raise ValueError(
                    f"duplicate protobuf symbol {full_name!r}: {previous} and {kind}"
                )
            symbols[full_name] = kind

        def add_message(
            proto: descriptor_pb2.DescriptorProto,
            file: FileDescriptor,
            prefix: str,
            parent: MessageDescriptor | None,
        ) -> MessageDescriptor:
            full_name = self._qualified(prefix, proto.name)
            claim(full_name, "message")
            message = MessageDescriptor(
                self, proto, full_name=full_name, file=file, containing_type=parent
            )
            messages[full_name] = message
            message.nested_types = tuple(
                add_message(item, file, full_name, message)
                for item in proto.nested_type
            )
            message.nested_types_by_name = MappingProxyType(
                {item.name: item for item in message.nested_types}
            )
            message.enum_types = tuple(
                add_enum(item, file, full_name, message) for item in proto.enum_type
            )
            message.enum_types_by_name = MappingProxyType(
                {item.name: item for item in message.enum_types}
            )
            return message

        def add_enum(
            proto: descriptor_pb2.EnumDescriptorProto,
            file: FileDescriptor,
            prefix: str,
            parent: MessageDescriptor | None,
        ) -> EnumDescriptor:
            full_name = self._qualified(prefix, proto.name)
            claim(full_name, "enum")
            enum = EnumDescriptor(
                self, proto, full_name=full_name, file=file, containing_type=parent
            )
            enums[full_name] = enum
            enum.values = tuple(
                EnumValueDescriptor(self, item, enum, index)
                for index, item in enumerate(proto.value)
            )
            values_by_name = {item.name: item for item in enum.values}
            if len(values_by_name) != len(enum.values):
                raise ValueError(f"duplicate value name in enum {full_name!r}")
            for value in enum.values:
                claim(value.full_name, "enum value")
            enum.values_by_name = MappingProxyType(values_by_name)
            by_number: dict[int, EnumValueDescriptor] = {}
            for value in enum.values:
                by_number.setdefault(value.number, value)
            enum.values_by_number = MappingProxyType(by_number)
            return enum

        for proto in protos:
            file = files[proto.name]
            file.dependencies = tuple(files[name] for name in proto.dependency)
            file.public_dependencies = tuple(
                file.dependencies[index] for index in proto.public_dependency
            )
            file_messages = tuple(
                add_message(item, file, proto.package, None)
                for item in proto.message_type
            )
            file.message_types_by_name = MappingProxyType(
                {item.name: item for item in file_messages}
            )
            file_enums = tuple(
                add_enum(item, file, proto.package, None) for item in proto.enum_type
            )
            file.enum_types_by_name = MappingProxyType(
                {item.name: item for item in file_enums}
            )
            file_services = tuple(
                ServiceDescriptor(
                    self,
                    item,
                    full_name=self._qualified(proto.package, item.name),
                    file=file,
                    index=index,
                )
                for index, item in enumerate(proto.service)
            )
            for service in file_services:
                claim(service.full_name, "service")
            file.services_by_name = MappingProxyType(
                {item.name: item for item in file_services}
            )
            services.update((item.full_name, item) for item in file_services)

        for message in messages.values():
            message_proto = message._proto
            oneof_names = [item.name for item in message_proto.oneof_decl]
            if len(oneof_names) != len(set(oneof_names)):
                raise ValueError(f"duplicate oneof name in {message.full_name!r}")
            field_names = [item.name for item in message_proto.field]
            field_numbers = [item.number for item in message_proto.field]
            if len(field_names) != len(set(field_names)) or len(field_numbers) != len(
                set(field_numbers)
            ):
                raise ValueError(f"duplicate field in {message.full_name!r}")
            message.oneofs = tuple(
                OneofDescriptor(self, item, message, index)
                for index, item in enumerate(message_proto.oneof_decl)
            )
            message.oneofs_by_name = MappingProxyType(
                {item.name: item for item in message.oneofs}
            )
            message.fields = tuple(
                self._field(item, message.file, message, index, messages, enums)
                for index, item in enumerate(message_proto.field)
            )
            message.fields_by_name = MappingProxyType(
                {item.name: item for item in message.fields}
            )
            message.fields_by_number = MappingProxyType(
                {item.number: item for item in message.fields}
            )
            message.fields_by_camelcase_name = MappingProxyType(
                {item.camelcase_name: item for item in message.fields}
            )
            message.enum_values_by_name = MappingProxyType(
                {
                    value.name: value
                    for enum in message.enum_types
                    for value in enum.values
                }
            )
            for field in message.fields:
                if field._proto.HasField("oneof_index"):
                    field.containing_oneof = message.oneofs[field._proto.oneof_index]
                    field.containing_oneof.fields += (field,)
                field.has_presence = (
                    field.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
                    and (
                        message.file.syntax == "proto2"
                        or field.type
                        == descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
                        or field.containing_oneof is not None
                    )
                )
                field.is_packed = self._is_packed(field)
                field.default_value = self._default_value(field)

            message_extensions = tuple(
                self._extension(
                    item,
                    message.file,
                    message,
                    index,
                    messages,
                    enums,
                )
                for index, item in enumerate(message._proto.extension)
            )
            message.extensions = message_extensions
            message.extensions_by_name = MappingProxyType(
                {item.name: item for item in message_extensions}
            )
            for extension in message_extensions:
                claim(extension.full_name, "extension")
                extensions[extension.full_name] = extension

        for file in files.values():
            file_extensions = tuple(
                self._extension(
                    item,
                    file,
                    None,
                    index,
                    messages,
                    enums,
                )
                for index, item in enumerate(file._proto.extension)
            )
            file.extensions_by_name = MappingProxyType(
                {item.name: item for item in file_extensions}
            )
            for extension in file_extensions:
                claim(extension.full_name, "extension")
                extensions[extension.full_name] = extension

        for service in services.values():
            method_names = [item.name for item in service._proto.method]
            if len(method_names) != len(set(method_names)):
                raise ValueError(f"duplicate method name in {service.full_name!r}")
            service.methods = tuple(
                MethodDescriptor(self, item, service, index)
                for index, item in enumerate(service._proto.method)
            )
            service.methods_by_name = MappingProxyType(
                {item.name: item for item in service.methods}
            )
            for method in service.methods:
                method.input_type = messages[method._proto.input_type.lstrip(".")]
                method.output_type = messages[method._proto.output_type.lstrip(".")]

        self.files_by_name = MappingProxyType(files)
        self.messages_by_name = MappingProxyType(messages)
        self.enums_by_name = MappingProxyType(enums)
        self.services_by_name = MappingProxyType(services)
        self.extensions_by_name = MappingProxyType(extensions)

    def _field(
        self,
        proto: descriptor_pb2.FieldDescriptorProto,
        file: FileDescriptor,
        message: MessageDescriptor,
        index: int,
        messages: Mapping[str, MessageDescriptor],
        enums: Mapping[str, EnumDescriptor],
    ) -> FieldDescriptor:
        field = FieldDescriptor(
            self,
            proto,
            full_name=f"{message.full_name}.{proto.name}",
            file=file,
            containing_type=message,
            index=index,
        )
        if proto.type in {
            descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
            descriptor_pb2.FieldDescriptorProto.TYPE_GROUP,
        }:
            field.message_type = messages[proto.type_name.lstrip(".")]
        elif proto.type == 14:
            field.enum_type = enums[proto.type_name.lstrip(".")]
        return field

    def _extension(
        self,
        proto: descriptor_pb2.FieldDescriptorProto,
        file: FileDescriptor,
        scope: MessageDescriptor | None,
        index: int,
        messages: Mapping[str, MessageDescriptor],
        enums: Mapping[str, EnumDescriptor],
    ) -> FieldDescriptor:
        prefix = scope.full_name if scope is not None else file.package
        extendee = messages[proto.extendee.lstrip(".")]
        field = FieldDescriptor(
            self,
            proto,
            full_name=self._qualified(prefix, proto.name),
            file=file,
            containing_type=extendee,
            index=index,
            is_extension=True,
        )
        field.extension_scope = scope
        if proto.type in {
            descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
            descriptor_pb2.FieldDescriptorProto.TYPE_GROUP,
        }:
            field.message_type = messages[proto.type_name.lstrip(".")]
        elif proto.type == descriptor_pb2.FieldDescriptorProto.TYPE_ENUM:
            field.enum_type = enums[proto.type_name.lstrip(".")]
        field.has_presence = (
            proto.label != descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
        )
        field.is_packed = self._is_packed(field)
        field.default_value = self._default_value(field)
        return field

    @staticmethod
    def _is_packed(field: FieldDescriptor) -> bool:
        packable = field.type not in {
            FieldDescriptor.TYPE_STRING,
            FieldDescriptor.TYPE_BYTES,
            FieldDescriptor.TYPE_MESSAGE,
            FieldDescriptor.TYPE_GROUP,
        }
        if not field.is_repeated or not packable:
            return False
        options = field._proto.options
        if options.HasField("packed"):
            return options.packed
        return field.file.syntax == "proto3"

    @staticmethod
    def _default_value(field: FieldDescriptor) -> Any:
        if field.is_repeated:
            return []
        if field.type in {FieldDescriptor.TYPE_MESSAGE, FieldDescriptor.TYPE_GROUP}:
            return None
        text = field._proto.default_value if field.has_default_value else None
        if field.type in {FieldDescriptor.TYPE_DOUBLE, FieldDescriptor.TYPE_FLOAT}:
            return float(text) if text is not None else 0.0
        if field.type == FieldDescriptor.TYPE_BOOL:
            return text == "true" if text is not None else False
        if field.type == FieldDescriptor.TYPE_STRING:
            return text or ""
        if field.type == FieldDescriptor.TYPE_BYTES:
            if text is None:
                return b""
            return _c_unescape_bytes(text)
        if field.type == FieldDescriptor.TYPE_ENUM:
            if field.enum_type is None:
                raise RuntimeError("enum field was not linked")
            if text is not None:
                return field.enum_type.values_by_name[text].number
            return field.enum_type.values[0].number
        return _parse_integer_default(text) if text is not None else 0

    def provider(self, facade: _Facade[Any]) -> Any:
        with self._provider_lock:
            if self._provider_pool is None:
                pool = descriptor_pool.DescriptorPool()
                pending = list(self._serialized_files)
                while pending:
                    remaining: list[bytes] = []
                    for raw in pending:
                        try:
                            pool.AddSerializedFile(  # type: ignore[no-untyped-call, unused-ignore]
                                raw
                            )
                        except TypeError:
                            remaining.append(raw)
                    if len(remaining) == len(pending):
                        raise RuntimeError(
                            "unable to link private provider descriptors"
                        )
                    pending = remaining
                self._provider_pool = pool
            pool = self._provider_pool
        if isinstance(facade, FileDescriptor):
            return pool.FindFileByName(  # type: ignore[no-untyped-call, unused-ignore]
                facade.name
            )
        if isinstance(facade, MessageDescriptor):
            return pool.FindMessageTypeByName(  # type: ignore[no-untyped-call, unused-ignore]
                facade.full_name
            )
        if isinstance(facade, EnumDescriptor):
            return pool.FindEnumTypeByName(  # type: ignore[no-untyped-call, unused-ignore]
                facade.full_name
            )
        if isinstance(facade, ServiceDescriptor):
            return pool.FindServiceByName(  # type: ignore[no-untyped-call, unused-ignore]
                facade.full_name
            )
        if isinstance(facade, FieldDescriptor) and facade.is_extension:
            return pool.FindExtensionByName(  # type: ignore[no-untyped-call, unused-ignore]
                facade.full_name
            )
        if isinstance(facade, FieldDescriptor):
            if facade.containing_type is None:
                raise LookupError(facade.full_name)
            return facade.containing_type.provider_descriptor.fields_by_name[
                facade.name
            ]
        if isinstance(facade, OneofDescriptor):
            return facade.containing_type.provider_descriptor.oneofs_by_name[
                facade.name
            ]
        if isinstance(facade, EnumValueDescriptor):
            return facade.type.provider_descriptor.values_by_name[facade.name]
        if isinstance(facade, MethodDescriptor):
            return facade.containing_service.provider_descriptor.methods_by_name[
                facade.name
            ]
        parent = facade.file.provider_descriptor
        return self._find_provider(parent, facade.full_name)

    @classmethod
    def _find_provider(cls, container: Any, full_name: str) -> Any:
        for collection in (
            "message_types_by_name",
            "enum_types_by_name",
            "services_by_name",
            "extensions_by_name",
            "fields_by_name",
            "oneofs_by_name",
            "methods_by_name",
            "values_by_name",
        ):
            value = getattr(container, collection, {}).get(full_name.rsplit(".", 1)[-1])
            if value is not None and getattr(value, "full_name", None) == full_name:
                return value
        for collection in (
            "message_types_by_name",
            "nested_types_by_name",
            "services_by_name",
            "enum_types_by_name",
        ):
            for nested in getattr(container, collection, {}).values():
                try:
                    return cls._find_provider(nested, full_name)
                except LookupError:
                    pass
        raise LookupError(full_name)
