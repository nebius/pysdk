from collections.abc import Iterable
from logging import getLogger
from typing import Sequence

import google.protobuf.descriptor_pb2 as pb

from nebius.base.protos.compiler.pygen import ImportedSymbol, ImportPath

log = getLogger(__name__)


class DescriptorError(Exception):
    pass


class FieldNotMessageError(DescriptorError):
    def __init__(self, field: "Field") -> None:
        super().__init__(
            f"Field {field.name} of {field.containing_message.full_type_name} is not "
            "a message type."
        )


class FieldNotEnumError(DescriptorError):
    def __init__(self, field: "Field") -> None:
        super().__init__(
            f"Field {field.name} of {field.containing_message.full_type_name} is not "
            "a enum type."
        )


class Descriptor:
    @property
    def name(self) -> str:
        return self.descriptor.name  # type: ignore


class EnumValue(Descriptor):
    def __init__(
        self,
        descriptor: pb.EnumValueDescriptorProto,
        containing_enum: "Enum",
    ) -> None:
        self.descriptor = descriptor
        self.containing_enum = containing_enum

    @property
    def number(self) -> int:
        return self.descriptor.number  # type:ignore[no-any-return,unused-ignore]

    @property
    def pb2(self) -> ImportedSymbol:
        c_import = self.containing_enum.pb2
        return ImportedSymbol(c_import.name + "." + self.name, c_import.import_path)


class Enum(Descriptor):
    def __init__(
        self,
        descriptor: pb.EnumDescriptorProto,
        containing_file: "File",
        containing_message: "Message|None" = None,
    ) -> None:
        self.descriptor = descriptor
        self.containing_message = containing_message
        self.containing_file = containing_file
        self._values: list[EnumValue] | None = None
        self._values_dict: dict[str, EnumValue] | None = None

    @property
    def values(self) -> list[EnumValue]:
        if self._values is None:
            self._values = [EnumValue(val, self) for val in self.descriptor.value]
        return self._values

    @property
    def values_dict(self) -> dict[str, EnumValue]:
        if self._values_dict is None:
            self._values_dict = {val.name: val for val in self.values}
        return self._values_dict

    @property
    def no_wrap(self) -> bool:
        if self.containing_file.skipped:
            return True
        return False

    @property
    def full_type_name(self) -> str:
        if self.containing_message is not None:
            return self.containing_message.full_type_name + "." + self.name
        return "." + self.containing_file.package + "." + self.name

    @property
    def export_path(self) -> ImportedSymbol:
        if self.containing_message is not None:
            c_import = self.containing_message.export_path
            return ImportedSymbol(c_import.name + "." + self.name, c_import.import_path)
        return ImportedSymbol(self.name, self.containing_file.export_path)

    @property
    def pb2(self) -> ImportedSymbol:
        if self.containing_message is not None:
            c_import = self.containing_message.pb2
            return ImportedSymbol(c_import.name + "." + self.name, c_import.import_path)
        return ImportedSymbol(self.name, self.containing_file.pb2)


class Field(Descriptor):
    def __init__(
        self,
        descriptor: pb.FieldDescriptorProto,
        containing_message: "Message",
    ) -> None:
        self.descriptor = descriptor
        self.containing_message = containing_message

    @property
    def message(self) -> "Message":
        if self.descriptor.type == self.descriptor.TYPE_MESSAGE:
            return self.containing_message.get_message_by_type_name(
                self.descriptor.type_name
            )
        else:
            raise FieldNotMessageError(self)

    @property
    def enum(self) -> "Enum":
        if self.descriptor.type == self.descriptor.TYPE_ENUM:
            return self.containing_message.get_enum_by_type_name(
                self.descriptor.type_name
            )
        else:
            raise FieldNotEnumError(self)

    def tracks_presence(self) -> bool:
        return (  # type:ignore[no-any-return,unused-ignore]
            self.descriptor.proto3_optional
            or (
                self.descriptor.type == self.descriptor.TYPE_MESSAGE
                and self.descriptor.label != self.descriptor.LABEL_REPEATED
            )
            or self.descriptor.HasField("oneof_index")
        )

    @property
    def map_key(self) -> "Field":
        return self.message.field_by_name("key")

    @property
    def map_value(self) -> "Field":
        return self.message.field_by_name("value")

    def python_type(self) -> ImportedSymbol:
        match self.descriptor.type:
            case self.descriptor.TYPE_DOUBLE | self.descriptor.TYPE_FLOAT:
                return ImportedSymbol("float", "builtins")
            case (
                self.descriptor.TYPE_INT64
                | self.descriptor.TYPE_UINT64
                | self.descriptor.TYPE_INT32
                | self.descriptor.TYPE_UINT32
                | self.descriptor.TYPE_FIXED64
                | self.descriptor.TYPE_FIXED32
                | self.descriptor.TYPE_SFIXED32
                | self.descriptor.TYPE_SFIXED64
                | self.descriptor.TYPE_SINT32
                | self.descriptor.TYPE_SINT64
            ):
                return ImportedSymbol("int", "builtins")
            case self.descriptor.TYPE_BOOL:
                return ImportedSymbol("bool", "builtins")
            case self.descriptor.TYPE_STRING:
                return ImportedSymbol("str", "builtins")
            case self.descriptor.TYPE_BYTES:
                return ImportedSymbol("bytes", "builtins")
            case self.descriptor.TYPE_ENUM:
                return self.enum.export_path
            case self.descriptor.TYPE_MESSAGE:
                return self.message.export_path
            case _:
                raise ValueError(f"Unsupported descriptor type: {self.descriptor.type}")

    def is_enum(self) -> bool:
        if self.descriptor.type == self.descriptor.TYPE_ENUM:
            return True
        return False

    def is_map(self) -> bool:
        return (
            self.descriptor.label == self.descriptor.LABEL_REPEATED
            and self.descriptor.type == self.descriptor.TYPE_MESSAGE
            and self.message.is_map_entry()
        )

    def is_repeated(self) -> bool:
        return (
            self.descriptor.label == self.descriptor.LABEL_REPEATED
            and not self.is_map()
        )

    def is_message(self) -> bool:
        if self.descriptor.type == self.descriptor.TYPE_MESSAGE:
            return True
        return False


class Message(Descriptor):
    def __init__(
        self,
        descriptor: pb.DescriptorProto,
        containing_file: "File",
        containing_message: "Message|None" = None,
    ) -> None:
        self.descriptor = descriptor
        self.containing_file = containing_file
        self.containing_message = containing_message
        self._messages: "list[Message]|None" = None
        self._messages_dict: "dict[str,Message]|None" = None
        self._fields: list[Field] | None = None
        self._fields_dict: dict[str, Field] | None = None
        self._enums_dict: dict[str, Enum] | None = None
        self.attached_names = dict[str, str]()

    @property
    def enums_dict(self) -> dict[str, Enum]:
        if self._enums_dict is None:
            self._enums_dict = {
                e.name: Enum(e, self.containing_file, self)
                for e in self.descriptor.enum_type
            }
        return self._enums_dict

    @property
    def enums(self) -> Iterable[Enum]:
        return self.enums_dict.values()

    @property
    def fields_dict(self) -> dict[str, Field]:
        if self._fields_dict is None:
            self._fields_dict = {field.name: field for field in self.fields()}
        return self._fields_dict

    @property
    def no_wrap(self) -> bool:
        if self.containing_file.skipped:
            return True
        return False

    @property
    def export_path(self) -> ImportedSymbol:
        if self.containing_message is not None:
            c_import = self.containing_message.export_path
            return ImportedSymbol(c_import.name + "." + self.name, c_import.import_path)
        return ImportedSymbol(self.name, self.containing_file.export_path)

    def field_by_name(self, name: str) -> Field:
        return self.fields_dict[name]

    def fields(self) -> list[Field]:
        if self._fields is None:
            self._fields = [Field(f, self) for f in self.descriptor.field]
        return self._fields

    @property
    def full_type_name(self) -> str:
        if self.containing_message is not None:
            return self.containing_message.full_type_name + "." + self.name
        return "." + self.containing_file.package + "." + self.name

    def get_message_by_type_name(self, name: str, strict: bool = False) -> "Message":
        if name[0] == ".":
            return self.containing_file.get_message_by_type_name(name)
        name_parts = name.split(".", 1)
        try:
            msg = self.message_by_name(name_parts[0])
            if len(name_parts) > 1:
                return msg.get_message_by_type_name(name_parts[1], strict=True)
            return msg
        except KeyError:
            if strict:
                raise KeyError(
                    f"Message {name} not found in scope of " f"{self.full_type_name}"
                )
            if self.containing_message is not None:
                return self.containing_message.get_message_by_type_name(name)
            else:
                return self.containing_file.get_message_by_type_name(name)

    def get_enum_by_type_name(self, name: str, strict: bool = False) -> "Enum":
        if name[0] == ".":
            return self.containing_file.get_enum_by_type_name(name)
        name_parts = name.split(".", 1)
        try:
            if len(name_parts) > 1:
                msg = self.message_by_name(name_parts[0])
                return msg.get_enum_by_type_name(name_parts[1], strict=True)
            return self.enums_dict[name_parts[0]]
        except KeyError:
            if strict:
                raise KeyError(
                    f"Enum {name} not found in scope of " f"{self.full_type_name}"
                )
            if self.containing_message is not None:
                return self.containing_message.get_enum_by_type_name(name)
            else:
                return self.containing_file.get_enum_by_type_name(name)

    def message_by_name(self, name: str) -> "Message":
        if self._messages_dict is None:
            self._messages_dict = {msg.name: msg for msg in self.messages()}
        return self._messages_dict[name]

    def messages(self) -> Sequence["Message"]:
        if self._messages is None:
            self._messages = [
                Message(msg, self.containing_file, self)
                for msg in self.descriptor.nested_type
            ]
        return self._messages

    def is_map_entry(self) -> bool:
        if self.descriptor.options.map_entry:
            return True
        return False

    @property
    def pb2(self) -> ImportedSymbol:
        if self.containing_message is not None:
            c_import = self.containing_message.pb2
            return ImportedSymbol(c_import.name + "." + self.name, c_import.import_path)
        return ImportedSymbol(self.name, self.containing_file.pb2)

    def collect_all_names(self) -> set[str]:
        ret = set[str](self.fields_dict.keys())
        for msg in self.messages():
            ret.add(msg.name)
            ret = ret.union(msg.collect_all_names())
        for enum in self.enums:
            ret.add(enum.name)
            ret = ret.union([v.name for v in enum.values])
        return ret


class File(Descriptor):
    def __init__(
        self,
        descriptor: pb.FileDescriptorProto,
        file_set: "FileSet",
    ) -> None:
        self.descriptor = descriptor
        self.global_set = file_set
        import_path = (
            self.descriptor.name.removesuffix(".proto").replace("/", ".") + "_pb2"
        )
        for prefix, subst in file_set.import_substitutions.items():
            if import_path.startswith(prefix + ".") or import_path == prefix:
                import_path = subst + import_path.removeprefix(prefix)
                break
        self.pb2: ImportPath = ImportPath(import_path)
        self.skipped: bool = self.global_set.is_package_skipped(self.package)
        if self.skipped:
            self.export_path: ImportPath = self.pb2
        else:
            export_path = self.descriptor.package
            export_substituted = False
            for prefix, subst in file_set.export_substitutions.items():
                if export_path.startswith(prefix + ".") or export_path == prefix:
                    export_path = subst + export_path.removeprefix(prefix)
                    export_substituted = True
                    break
            if not export_substituted:
                for prefix, subst in file_set.import_substitutions.items():
                    if export_path.startswith(prefix + ".") or export_path == prefix:
                        export_path = subst + export_path.removeprefix(prefix)
                        break
            self.export_path = ImportPath(export_path)
        self._messages: list[Message] | None = None
        self._messages_dict: dict[str, Message] | None = None
        self._deps_dict: dict[str, File] | None = None
        self._enums_dict: dict[str, Enum] | None = None

    def collect_all_names(self, with_locals: bool = True) -> set[str]:
        ret = set[str](self.package.split("."))
        for msg in self.messages():
            ret.add(msg.name)
            if with_locals:
                ret = ret.union(msg.collect_all_names())
        for enum in self.enums:
            ret.add(enum.name)
            ret = ret.union([v.name for v in enum.values])
        if with_locals:
            for dep in self.dependencies.values():
                ret = ret.union(dep.collect_all_names(True))
        return ret

    def get_message_by_type_name(self, name: str, strict: bool = False) -> "Message":
        name_partial = name
        if name_partial[0] == ".":
            if name_partial.startswith("." + self.package + "."):
                strict = True
                name_partial = name_partial.removeprefix("." + self.package + ".")
        name_parts = name_partial.split(".", 1)
        try:
            msg = self.message_by_name(name_parts[0])
            if len(name_parts) > 1:
                return msg.get_message_by_type_name(name_parts[1], strict=True)
            return msg
        except KeyError:
            for dep in self.dependencies.values():
                if (
                    strict
                    and dep.package != self.package
                    and not dep.package.startswith(self.package + ".")
                ):
                    continue
                try:
                    return dep.get_message_by_type_name(name)
                except KeyError:
                    pass
            raise KeyError(f"Message {name} not found in scope of {self.name}")

    def get_enum_by_type_name(self, name: str, strict: bool = False) -> "Enum":
        name_partial = name
        if name_partial[0] == ".":
            if name_partial.startswith("." + self.package + "."):
                strict = True
                name_partial = name_partial.removeprefix("." + self.package + ".")
        name_parts = name_partial.split(".", 1)
        try:
            if len(name_parts) > 1:
                msg = self.message_by_name(name_parts[0])
                return msg.get_enum_by_type_name(name_parts[1], strict=True)
            return self.enums_dict[name_parts[0]]
        except KeyError:
            for dep in self.dependencies.values():
                if (
                    strict
                    and dep.package != self.package
                    and not dep.package.startswith(self.package + ".")
                ):
                    continue
                try:
                    return dep.get_enum_by_type_name(name)
                except KeyError:
                    pass
            raise KeyError(f"Enum {name} not found in scope of {self.name}")

    @property
    def dependencies(self) -> "dict[str, File]":
        if self._deps_dict is None:
            self._deps_dict = {
                name: self.global_set.file_by_name(name)
                for name in self.descriptor.dependency
            }
        return self._deps_dict

    @property
    def package(self) -> str:
        return str(self.descriptor.package)

    def message_by_name(self, name: str) -> Message:
        if self._messages_dict is None:
            self._messages_dict = {msg.name: msg for msg in self.messages()}
        return self._messages_dict[name]

    def messages(self) -> Sequence[Message]:
        if self._messages is None:
            self._messages = [
                Message(msg, self) for msg in self.descriptor.message_type
            ]
        return self._messages

    @property
    def enums_dict(self) -> dict[str, Enum]:
        if self._enums_dict is None:
            self._enums_dict = {
                e.name: Enum(e, self) for e in self.descriptor.enum_type
            }
        return self._enums_dict

    @property
    def enums(self) -> Iterable[Enum]:
        return self.enums_dict.values()

    @property
    def grpc(self) -> ImportPath:
        p = self.pb2
        return ImportPath(p.import_path + "_grpc")


class FileSet(Descriptor):
    def __init__(
        self,
        file_set: Sequence[pb.FileDescriptorProto],
        import_substitutions: dict[str, str] | None = None,
        export_substitutions: dict[str, str] | None = None,
        skip_packages: list[str] | None = None,
    ):
        if import_substitutions is None:
            import_substitutions = dict[str, str]()
        if export_substitutions is None:
            export_substitutions = dict[str, str]()
        if skip_packages is None:
            skip_packages = list[str]()

        self.import_substitutions = import_substitutions
        self.export_substitutions = export_substitutions
        self.skip_packages = set(skip_packages)

        self._file_set = [File(file, self) for file in file_set]
        self._files_dict: dict[str, File] | None = None

    def is_package_skipped(self, package: str) -> bool:
        for pkg in self.skip_packages:
            if package == pkg or package.startswith(pkg + "."):
                return True
        return False

    def collect_names(self, package: str) -> set[str]:
        ret = set[str](package.split("."))
        for file in self.files:
            if file.package == package:
                ret = ret.union(file.collect_all_names())
        return ret

    def file_by_name(self, name: str) -> "File":
        return self.files_dict[name]

    @property
    def files_dict(self) -> dict[str, File]:
        if self._files_dict is None:
            self._files_dict = {file.name: file for file in self._file_set}
        return self._files_dict

    @property
    def files(self) -> Sequence[File]:
        return self._file_set
