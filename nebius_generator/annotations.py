"""Public Nebius annotation policies used by the generator."""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from nebius.api._registry import REGISTRY as _COMMITTED_API_REGISTRY
from nebius.api.google.protobuf import (
    EnumOptions,
    EnumValueOptions,
    FieldDescriptorProto,
    FieldOptions,
    FileDescriptorProto,
    FileOptions,
    MessageOptions,
    MethodOptions,
    OneofOptions,
    ServiceOptions,
)

from .bootstrap import FrozenMessage
from .errors import GeneratorError
from .options import (
    SerializableOptions,
    bool_option,
    length_delimited,
    nested_string_option,
    option_bytes,
    repeated_varints,
)

NameKind = Literal["class", "field", "method", "enum_value"]

_CLASS_NAME = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
_MEMBER_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_ENUM_VALUE_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")

_OPTION_TYPES = {
    "file": FileOptions,
    "message": MessageOptions,
    "field": FieldOptions,
    "oneof": OneofOptions,
    "enum": EnumOptions,
    "enum_value": EnumValueOptions,
    "service": ServiceOptions,
    "method": MethodOptions,
}

_TYPE_BOOL = int(FieldDescriptorProto.Type.TYPE_BOOL)
_TYPE_STRING = int(FieldDescriptorProto.Type.TYPE_STRING)
_TYPE_MESSAGE = int(FieldDescriptorProto.Type.TYPE_MESSAGE)
_TYPE_ENUM = int(FieldDescriptorProto.Type.TYPE_ENUM)
_LABEL_OPTIONAL = int(FieldDescriptorProto.Label.LABEL_OPTIONAL)
_LABEL_REPEATED = int(FieldDescriptorProto.Label.LABEL_REPEATED)


def _signed_enum_number(value: int) -> int:
    value &= (1 << 32) - 1
    return value - (1 << 32) if value & (1 << 31) else value


@dataclass(frozen=True)
class Deprecation:
    """Generator-owned view of standard and Nebius deprecation options."""

    effective_at: str = ""
    description: str = ""

    def summary(self) -> str:
        parts: list[str] = []
        if self.effective_at:
            try:
                effective = date.fromisoformat(self.effective_at)
            except ValueError as error:
                raise GeneratorError(
                    f"invalid deprecation date {self.effective_at!r}"
                ) from error
            parts.append(f"Supported until {effective:%m/%d/%y}.")
        if self.description:
            description = self.description[0].upper() + self.description[1:]
            if not description.endswith("."):
                description += "."
            parts.append(description)
        return " ".join(parts) or "Deprecated."


class Annotations:
    """Read the public annotation schema from the current generation request."""

    def __init__(self, files: dict[str, FrozenMessage]):
        schema = files.get("nebius/annotations.proto")
        if schema is None:
            descriptor = _COMMITTED_API_REGISTRY.file_descriptor(
                "nebius/annotations.proto"
            )
            schema = FileDescriptorProto.FromString(descriptor.serialized_pb)
        package = schema.package
        self._extensions = {extension.name: extension for extension in schema.extension}
        self._messages = {
            f"{package}.{message.name}": message for message in schema.message_type
        }
        self._enums = {f"{package}.{enum.name}": enum for enum in schema.enum_type}

    @staticmethod
    def _extendee(option_kind: str) -> str:
        option_type = _OPTION_TYPES[option_kind]
        return f".{option_type.__PROTO_FULL_NAME__}"

    def _extension(
        self,
        name: str,
        option_kind: str,
        type_: int,
        *,
        repeated: bool = False,
    ) -> FrozenMessage:
        extension = self._extensions.get(name)
        if extension is None:
            raise GeneratorError(f"missing public annotation {name!r}")
        label = _LABEL_REPEATED if repeated else _LABEL_OPTIONAL
        if (
            extension.extendee != self._extendee(option_kind)
            or extension.type != type_
            or extension.label != label
        ):
            raise GeneratorError(f"incompatible public annotation {name!r}")
        return extension

    def _message_field(
        self,
        extension: FrozenMessage,
        field_name: str,
        type_: int,
    ) -> FrozenMessage:
        message = self._messages.get(extension.type_name.lstrip("."))
        field = (
            next(
                (item for item in message.field if item.name == field_name),
                None,
            )
            if message is not None
            else None
        )
        if field is None or field.type != type_:
            target = extension.type_name.lstrip(".") or "<missing>"
            raise GeneratorError(f"incompatible annotation message {target!r}")
        return field

    def _nested_string(
        self,
        options: SerializableOptions | bytes,
        extension_name: str,
        option_kind: str,
        field_name: str,
    ) -> str:
        extension = self._extension(extension_name, option_kind, _TYPE_MESSAGE)
        field = self._message_field(extension, field_name, _TYPE_STRING)
        return nested_string_option(options, extension.number, field.number)

    def _string(
        self,
        options: SerializableOptions | bytes,
        extension_name: str,
        option_kind: str,
    ) -> str:
        extension = self._extension(extension_name, option_kind, _TYPE_STRING)
        values = length_delimited(options, extension.number)
        if not values:
            return ""
        try:
            return values[-1].decode("utf-8")
        except UnicodeDecodeError as error:
            raise GeneratorError("protobuf option string is not UTF-8") from error

    def deprecation(
        self,
        options: SerializableOptions | bytes,
        option_kind: str,
    ) -> Deprecation | None:
        """Return details when the dogfooded standard deprecated bit is set."""
        option_type = _OPTION_TYPES[option_kind]
        standard_options = option_type.FromString(option_bytes(options))
        if not standard_options.deprecated:
            return None
        extension_name = f"{option_kind}_deprecation_details"
        return Deprecation(
            effective_at=self._nested_string(
                options, extension_name, option_kind, "effective_at"
            ),
            description=self._nested_string(
                options, extension_name, option_kind, "description"
            ),
        )

    def python_name(
        self,
        options: SerializableOptions | bytes,
        option_kind: str,
        fallback: str,
        name_kind: NameKind,
    ) -> str:
        """Resolve and validate a py-sdk name override."""
        annotated = self._nested_string(
            options, f"{option_kind}_py_sdk", option_kind, "name"
        )
        if not annotated:
            return fallback
        if keyword.iskeyword(annotated) or keyword.issoftkeyword(annotated):
            raise GeneratorError(f"annotated Python name is reserved: {annotated!r}")
        pattern = {
            "class": _CLASS_NAME,
            "field": _MEMBER_NAME,
            "method": _MEMBER_NAME,
            "enum_value": _ENUM_VALUE_NAME,
        }[name_kind]
        if pattern.fullmatch(annotated) is None:
            raise GeneratorError(
                f"invalid annotated Python {name_kind} name {annotated!r}"
            )
        return annotated

    def api_service_name(self, options: SerializableOptions | bytes) -> str:
        return self._string(options, "api_service_name", "service")

    def method_is_updater(self, options: SerializableOptions | bytes) -> bool | None:
        extension = self._extension(
            "method_behavior", "method", _TYPE_ENUM, repeated=True
        )
        values = tuple(
            _signed_enum_number(value)
            for value in repeated_varints(options, extension.number)
        )
        if not values:
            return None
        enum = self._enums.get(extension.type_name.lstrip("."))
        if enum is None:
            raise GeneratorError(
                f"incompatible annotation enum {extension.type_name!r}"
            )
        updater_values = {
            value.number for value in enum.value if value.name == "METHOD_UPDATER"
        }
        return any(value in updater_values for value in values)

    def sensitive(self, options: SerializableOptions | bytes) -> bool:
        extension = self._extension("sensitive", "field", _TYPE_BOOL)
        return bool_option(options, extension.number)

    def credentials(self, options: SerializableOptions | bytes) -> bool:
        extension = self._extension("credentials", "field", _TYPE_BOOL)
        return bool_option(options, extension.number)
