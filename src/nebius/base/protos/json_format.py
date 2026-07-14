"""In-house ProtoJSON conversion for direct protobuf messages."""

from __future__ import annotations

import base64
import json
import math
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, TypeVar, cast

from .codec import STRING, ValueCodec
from .containers import MapValues
from .direct import Field, Message
from .extensions import Extension, RepeatedValues

M = TypeVar("M", bound=Message)
_SKIP = object()
_FLOAT32_MAX = 3.4028234663852886e38
_TIMESTAMP_MIN = -62_135_596_800
_TIMESTAMP_MAX = 253_402_300_799
_DURATION_MAX = 315_576_000_000
_WRAPPERS = {
    "google.protobuf.BoolValue",
    "google.protobuf.BytesValue",
    "google.protobuf.DoubleValue",
    "google.protobuf.FloatValue",
    "google.protobuf.Int32Value",
    "google.protobuf.Int64Value",
    "google.protobuf.StringValue",
    "google.protobuf.UInt32Value",
    "google.protobuf.UInt64Value",
}
_ANY_VALUE_TYPES = _WRAPPERS | {
    "google.protobuf.Any",
    "google.protobuf.Duration",
    "google.protobuf.FieldMask",
    "google.protobuf.ListValue",
    "google.protobuf.Struct",
    "google.protobuf.Timestamp",
    "google.protobuf.Value",
}


class JsonError(ValueError):
    """Raised when a value does not satisfy ProtoJSON rules."""


def _json_name(field: Field) -> str:
    if field.json_name is not None:
        return field.json_name
    parts = field.proto_name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _encode_value(
    codec: ValueCodec[Any],
    value: Any,
    *,
    preserving_proto_field_name: bool,
    always_print_fields_with_no_presence: bool,
    use_integers_for_enums: bool,
) -> Any:
    kind = codec.json_kind
    if kind in {"int64", "uint64"}:
        return str(value)
    if kind in {"int32", "uint32", "bool", "string"}:
        return value
    if kind in {"float", "double"}:
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if kind == "bytes":
        return base64.b64encode(value).decode("ascii")
    if kind == "enum":
        if not use_integers_for_enums and codec.enum_names is not None:
            name = codec.enum_names.get(value)
            if name is not None:
                return name
        return value
    if kind == "message":
        return message_to_value(
            cast(Message, value),
            preserving_proto_field_name=preserving_proto_field_name,
            always_print_fields_with_no_presence=always_print_fields_with_no_presence,
            use_integers_for_enums=use_integers_for_enums,
        )
    raise JsonError(f"unsupported ProtoJSON codec kind {kind!r}")


def _field(message: Message, name: str) -> Field:
    try:
        return message.__class__._fields_by_proto_name()[name]
    except KeyError as error:
        raise JsonError(
            f"{message.__PROTO_FULL_NAME__} is missing WKT field {name!r}"
        ) from error


def _get(message: Message, name: str) -> Any:
    return message._get_field(_field(message, name))


def _set(message: Message, name: str, value: Any) -> None:
    message._set_field(_field(message, name), value)


def _fraction(nanos: int) -> str:
    if nanos == 0:
        return ""
    digits = 3 if nanos % 1_000_000 == 0 else 6 if nanos % 1_000 == 0 else 9
    return f".{nanos:09d}"[: digits + 1]


def _encode_well_known(
    message: Message,
    *,
    preserving_proto_field_name: bool,
    always_print_fields_with_no_presence: bool,
    use_integers_for_enums: bool,
) -> tuple[bool, Any]:
    name = message.__PROTO_FULL_NAME__
    if name == "google.protobuf.Timestamp":
        seconds = cast(int, _get(message, "seconds"))
        nanos = cast(int, _get(message, "nanos"))
        if (
            not _TIMESTAMP_MIN <= seconds <= _TIMESTAMP_MAX
            or not 0 <= nanos < 1_000_000_000
        ):
            raise JsonError("Timestamp is outside its valid range")
        stamp = datetime(1970, 1, 1) + timedelta(seconds=seconds)
        rendered = (
            f"{stamp.year:04d}-{stamp.month:02d}-{stamp.day:02d}"
            f"T{stamp.hour:02d}:{stamp.minute:02d}:{stamp.second:02d}"
        )
        return True, rendered + _fraction(nanos) + "Z"
    if name == "google.protobuf.Duration":
        seconds = cast(int, _get(message, "seconds"))
        nanos = cast(int, _get(message, "nanos"))
        valid = (
            -_DURATION_MAX <= seconds <= _DURATION_MAX
            and -999_999_999 <= nanos <= 999_999_999
            and not (seconds < 0 < nanos or seconds > 0 > nanos)
        )
        if not valid:
            raise JsonError("Duration is outside its valid range")
        negative = seconds < 0 or nanos < 0
        return True, (
            ("-" if negative else "") + str(abs(seconds)) + _fraction(abs(nanos)) + "s"
        )
    if name == "google.protobuf.FieldMask":
        return True, ",".join(_snake_to_camel(path) for path in _get(message, "paths"))
    if name == "google.protobuf.Struct":
        fields = cast(MapValues[str, Message], _get(message, "fields"))
        return True, {
            key: message_to_value(
                value,
                preserving_proto_field_name=preserving_proto_field_name,
                always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                use_integers_for_enums=use_integers_for_enums,
            )
            for key, value in fields.items()
        }
    if name == "google.protobuf.ListValue":
        return True, [
            message_to_value(
                value,
                preserving_proto_field_name=preserving_proto_field_name,
                always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                use_integers_for_enums=use_integers_for_enums,
            )
            for value in cast(RepeatedValues[Message], _get(message, "values"))
        ]
    if name == "google.protobuf.Value":
        selected = message.WhichOneof("kind")
        if selected is None or selected == "null_value":
            return True, None
        if selected == "number_value":
            value = cast(float, _get(message, selected))
            if not math.isfinite(value):
                raise JsonError("Value cannot contain a non-finite number")
            return True, value
        if selected in {"string_value", "bool_value"}:
            return True, _get(message, selected)
        return True, message_to_value(
            cast(Message, _get(message, selected)),
            preserving_proto_field_name=preserving_proto_field_name,
            always_print_fields_with_no_presence=always_print_fields_with_no_presence,
            use_integers_for_enums=use_integers_for_enums,
        )
    if name in _WRAPPERS:
        value_field = _field(message, "value")
        return True, _encode_value(
            value_field.codec,
            message._get_field(value_field),
            preserving_proto_field_name=preserving_proto_field_name,
            always_print_fields_with_no_presence=always_print_fields_with_no_presence,
            use_integers_for_enums=use_integers_for_enums,
        )
    if name == "google.protobuf.Any":
        type_url = cast(str, _get(message, "type_url"))
        payload = cast(bytes, _get(message, "value"))
        if not type_url and not payload:
            return True, {}
        registry = message.__class__.__REGISTRY__
        if registry is None:
            raise JsonError("Any ProtoJSON requires a namespace registry")
        try:
            embedded = registry.unpack_any(message)
        except (LookupError, TypeError, ValueError) as error:
            raise JsonError(str(error)) from error
        result: dict[str, Any] = {"@type": type_url}
        if embedded.__PROTO_FULL_NAME__ in _ANY_VALUE_TYPES:
            result["value"] = message_to_value(
                embedded,
                preserving_proto_field_name=preserving_proto_field_name,
                always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                use_integers_for_enums=use_integers_for_enums,
            )
        else:
            result.update(
                message_to_dict(
                    embedded,
                    preserving_proto_field_name=preserving_proto_field_name,
                    always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                    use_integers_for_enums=use_integers_for_enums,
                )
            )
        return True, result
    if name == "google.protobuf.Empty":
        return True, {}
    return False, None


def message_to_value(
    message: Message,
    *,
    preserving_proto_field_name: bool = False,
    always_print_fields_with_no_presence: bool = False,
    use_integers_for_enums: bool = False,
) -> Any:
    """Convert a direct message to its ProtoJSON value."""
    handled, value = _encode_well_known(
        message,
        preserving_proto_field_name=preserving_proto_field_name,
        always_print_fields_with_no_presence=always_print_fields_with_no_presence,
        use_integers_for_enums=use_integers_for_enums,
    )
    if handled:
        return value
    return message_to_dict(
        message,
        preserving_proto_field_name=preserving_proto_field_name,
        always_print_fields_with_no_presence=always_print_fields_with_no_presence,
        use_integers_for_enums=use_integers_for_enums,
    )


def _encode_map_key(codec: ValueCodec[Any], value: Any) -> str:
    if codec.json_kind == "bool":
        return "true" if value else "false"
    return str(value)


def message_to_dict(
    message: Message,
    *,
    preserving_proto_field_name: bool = False,
    always_print_fields_with_no_presence: bool = False,
    use_integers_for_enums: bool = False,
) -> dict[str, Any]:
    """Convert a direct message to a ProtoJSON-compatible dictionary."""
    result: dict[str, Any] = {}
    for field in message.__FIELDS__:
        if not field.public:
            continue
        value = message._values.get(field)
        encoded: Any
        if field.map:
            if not value and not always_print_fields_with_no_presence:
                continue
            key_codec = cast(ValueCodec[Any], field.map_key_codec)
            encoded = {
                _encode_map_key(key_codec, key): _encode_value(
                    field.codec,
                    item,
                    preserving_proto_field_name=preserving_proto_field_name,
                    always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                    use_integers_for_enums=use_integers_for_enums,
                )
                for key, item in (
                    cast(MapValues[Any, Any], value).items() if value else ()
                )
            }
        elif field.repeated:
            if not value and not always_print_fields_with_no_presence:
                continue
            encoded = [
                _encode_value(
                    field.codec,
                    item,
                    preserving_proto_field_name=preserving_proto_field_name,
                    always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                    use_integers_for_enums=use_integers_for_enums,
                )
                for item in (cast(RepeatedValues[Any], value) if value else ())
            ]
        elif field.has_presence:
            if field not in message._present:
                continue
            encoded = _encode_value(
                field.codec,
                value,
                preserving_proto_field_name=preserving_proto_field_name,
                always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                use_integers_for_enums=use_integers_for_enums,
            )
        else:
            current = field.default() if value is None else value
            if current == field.default() and not always_print_fields_with_no_presence:
                continue
            encoded = _encode_value(
                field.codec,
                current,
                preserving_proto_field_name=preserving_proto_field_name,
                always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                use_integers_for_enums=use_integers_for_enums,
            )
        result[
            field.proto_name if preserving_proto_field_name else _json_name(field)
        ] = encoded
    if message._extensions is not None:
        for extension, value in message._extensions.present_items():
            if not extension.public:
                continue
            if extension.repeated:
                encoded_extension = [
                    _encode_value(
                        extension.value_codec,
                        item,
                        preserving_proto_field_name=preserving_proto_field_name,
                        always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                        use_integers_for_enums=use_integers_for_enums,
                    )
                    for item in cast(RepeatedValues[Any], value)
                ]
            else:
                encoded_extension = _encode_value(
                    extension.value_codec,
                    value,
                    preserving_proto_field_name=preserving_proto_field_name,
                    always_print_fields_with_no_presence=always_print_fields_with_no_presence,
                    use_integers_for_enums=use_integers_for_enums,
                )
            result[f"[{extension.full_name}]"] = encoded_extension
    return result


def _parse_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise JsonError("integer field does not accept bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, str) and " " not in value:
        try:
            return int(value)
        except ValueError:
            try:
                parsed = float(value)
            except ValueError:
                pass
            else:
                if math.isfinite(parsed) and parsed.is_integer():
                    return int(parsed)
    raise JsonError("invalid ProtoJSON integer")


def _parse_value(codec: ValueCodec[Any], value: Any, *, ignore_unknown: bool) -> Any:
    kind = codec.json_kind
    try:
        if kind in {"int32", "uint32", "int64", "uint64"}:
            return codec.normalize(_parse_integer(value))
        if kind == "bool":
            if not isinstance(value, bool):
                raise JsonError("bool field requires a JSON bool")
            return codec.normalize(value)
        if kind == "string":
            if not isinstance(value, str):
                raise JsonError("string field requires a JSON string")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as error:
                raise JsonError(
                    "string field contains an unpaired surrogate"
                ) from error
            return codec.normalize(value)
        if kind in {"float", "double"}:
            if isinstance(value, str):
                special = {
                    "NaN": math.nan,
                    "Infinity": math.inf,
                    "-Infinity": -math.inf,
                }
                parsed = special.get(value)
                if parsed is None:
                    parsed = float(value)
                    if value == "nan":
                        raise JsonError(
                            "NaN requires the exact ProtoJSON spelling 'NaN'"
                        )
            elif isinstance(value, (int, float)):
                parsed = float(value)
                if not math.isfinite(parsed):
                    raise JsonError(
                        "non-finite floats require a quoted ProtoJSON spelling"
                    )
                if (
                    kind == "float"
                    and isinstance(value, float)
                    and not -_FLOAT32_MAX <= value <= _FLOAT32_MAX
                ):
                    raise JsonError("float value is outside the float32 range")
            else:
                raise JsonError("invalid ProtoJSON float")
            return codec.normalize(parsed)
        if kind == "bytes":
            if not isinstance(value, str):
                raise JsonError("bytes field requires a base64 string")
            compact = "".join(value.split())
            padded = compact + "=" * (-len(compact) % 4)
            return codec.normalize(base64.urlsafe_b64decode(padded))
        if kind == "enum":
            if isinstance(value, str):
                if codec.enum_numbers is not None and value in codec.enum_numbers:
                    return codec.normalize(codec.enum_numbers[value])
                try:
                    number = int(value)
                except ValueError:
                    if ignore_unknown:
                        return _SKIP
                    raise JsonError(f"unknown enum name {value!r}") from None
                return codec.normalize(number)
            return codec.normalize(_parse_integer(value))
        if kind == "message":
            message = codec.default()
            parse_value(
                value,
                cast(Message, message),
                ignore_unknown_fields=ignore_unknown,
            )
            return message
    except (TypeError, ValueError, OverflowError) as error:
        if isinstance(error, JsonError):
            raise
        raise JsonError(str(error)) from error
    raise JsonError(f"unsupported ProtoJSON codec kind {kind!r}")


def _parse_map_key(codec: ValueCodec[Any], key: Any) -> Any:
    if not isinstance(key, str):
        raise JsonError("ProtoJSON map keys must be strings")
    if codec.json_kind == "string":
        try:
            key.encode("utf-8")
        except UnicodeEncodeError as error:
            raise JsonError("map key contains an unpaired surrogate") from error
        return codec.normalize(key)
    if codec.json_kind == "bool":
        if key == "true":
            return True
        if key == "false":
            return False
        raise JsonError("bool map key must be 'true' or 'false'")
    return codec.normalize(_parse_integer(key))


def _accepts_null(codec: ValueCodec[Any]) -> bool:
    if codec.json_kind != "message":
        return False
    value = codec.default()
    return (
        isinstance(value, Message)
        and value.__PROTO_FULL_NAME__ == "google.protobuf.Value"
    )


def _snake_to_camel(path: str) -> str:
    result: list[str] = []
    capitalize = False
    for character in path:
        if character.isupper():
            raise JsonError(f"FieldMask path {path!r} contains uppercase letters")
        if character == "_":
            if capitalize:
                raise JsonError(f"FieldMask path {path!r} has consecutive underscores")
            capitalize = True
        elif capitalize:
            if not character.islower():
                raise JsonError(
                    f"underscore in FieldMask path {path!r} must precede a letter"
                )
            result.append(character.upper())
            capitalize = False
        else:
            result.append(character)
    if capitalize:
        raise JsonError(f"FieldMask path {path!r} has a trailing underscore")
    return "".join(result)


def _camel_to_snake(path: str) -> str:
    if "_" in path:
        raise JsonError(f"FieldMask JSON path {path!r} contains an underscore")
    result: list[str] = []
    for character in path:
        if character.isupper():
            result.extend(("_", character.lower()))
        else:
            result.append(character)
    return "".join(result)


def _parse_timestamp(value: Any, message: Message) -> None:
    if not isinstance(value, str):
        raise JsonError("Timestamp requires an RFC 3339 string")
    try:
        zone_position = value.find("Z")
        if zone_position == -1:
            zone_position = value.find("+")
        if zone_position == -1:
            zone_position = value.rfind("-")
        if zone_position == -1:
            raise ValueError("missing timezone offset")
        time_value = value[:zone_position]
        point_position = time_value.find(".")
        if point_position == -1:
            base = time_value
            fraction = ""
        else:
            base = time_value[:point_position]
            fraction = time_value[point_position + 1 :]
        if "t" in base:
            raise ValueError("lowercase 't' is not accepted")
        local = datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
        if len(fraction) > 9:
            raise ValueError("Timestamp has more than 9 fractional digits")
        nanos = round(float("0." + fraction) * 1_000_000_000) if fraction else 0
        if value[zone_position] == "Z":
            if len(value) != zone_position + 1:
                raise ValueError("invalid trailing Timestamp data")
            offset = 0
        else:
            zone_text = value[zone_position:]
            colon = zone_text.find(":")
            if colon == -1:
                raise ValueError("invalid timezone offset")
            offset = (int(zone_text[1:colon]) * 60 + int(zone_text[colon + 1 :])) * 60
            if zone_text[0] == "-":
                offset = -offset
    except (OverflowError, ValueError) as error:
        raise JsonError(str(error)) from error
    delta = local - datetime(1970, 1, 1)
    seconds = delta.days * 86_400 + delta.seconds - offset
    if (
        not _TIMESTAMP_MIN <= seconds <= _TIMESTAMP_MAX
        or not 0 <= nanos < 1_000_000_000
    ):
        raise JsonError("Timestamp is outside its valid range")
    _set(message, "seconds", seconds)
    _set(message, "nanos", nanos)


def _parse_duration(value: Any, message: Message) -> None:
    if not isinstance(value, str):
        raise JsonError("Duration requires a string")
    if not value.endswith("s"):
        raise JsonError("Duration must end with 's'")
    try:
        point = value.find(".")
        if point == -1:
            seconds = int(value[:-1])
            nanos = 0
        else:
            seconds = int(value[:point])
            fraction = value[point:-1]
            prefix = "-0" if value.startswith("-") else "0"
            nanos = round(float(prefix + fraction) * 1_000_000_000)
    except (OverflowError, ValueError) as error:
        raise JsonError(str(error)) from error
    if (
        not -_DURATION_MAX <= seconds <= _DURATION_MAX
        or not -999_999_999 <= nanos <= 999_999_999
        or seconds < 0 < nanos
        or seconds > 0 > nanos
    ):
        raise JsonError("Duration is outside its valid range")
    _set(message, "seconds", seconds)
    _set(message, "nanos", nanos)


def _parse_well_known(
    value: Any, message: Message, *, ignore_unknown_fields: bool
) -> bool:
    name = message.__PROTO_FULL_NAME__
    if name == "google.protobuf.Timestamp":
        _parse_timestamp(value, message)
        return True
    if name == "google.protobuf.Duration":
        _parse_duration(value, message)
        return True
    if name == "google.protobuf.FieldMask":
        if not isinstance(value, str):
            raise JsonError("FieldMask requires a comma-separated string")
        _set(
            message,
            "paths",
            [] if not value else [_camel_to_snake(path) for path in value.split(",")],
        )
        return True
    if name == "google.protobuf.Struct":
        if not isinstance(value, Mapping):
            raise JsonError("Struct requires a JSON object")
        field = _field(message, "fields")
        parsed: dict[str, Message] = {}
        for key, item in value.items():
            normalized_key = _parse_map_key(STRING, key)
            child = cast(Message, field.codec.default())
            parse_value(item, child, ignore_unknown_fields=ignore_unknown_fields)
            parsed[normalized_key] = child
        message._set_field(field, parsed)
        return True
    if name == "google.protobuf.ListValue":
        if not isinstance(value, list):
            raise JsonError("ListValue requires a JSON array")
        field = _field(message, "values")
        parsed_values: list[Message] = []
        for item in value:
            child = cast(Message, field.codec.default())
            parse_value(item, child, ignore_unknown_fields=ignore_unknown_fields)
            parsed_values.append(child)
        message._set_field(field, parsed_values)
        return True
    if name == "google.protobuf.Value":
        if value is None:
            _set(message, "null_value", 0)
        elif isinstance(value, bool):
            _set(message, "bool_value", value)
        elif isinstance(value, (int, float)):
            number = float(value)
            if not math.isfinite(number):
                raise JsonError("Value cannot contain a non-finite number")
            _set(message, "number_value", number)
        elif isinstance(value, str):
            _set(
                message,
                "string_value",
                _parse_value(STRING, value, ignore_unknown=ignore_unknown_fields),
            )
        elif isinstance(value, Mapping):
            field = _field(message, "struct_value")
            child = cast(Message, field.codec.default())
            parse_value(value, child, ignore_unknown_fields=ignore_unknown_fields)
            message._set_field(field, child)
        elif isinstance(value, list):
            field = _field(message, "list_value")
            child = cast(Message, field.codec.default())
            parse_value(value, child, ignore_unknown_fields=ignore_unknown_fields)
            message._set_field(field, child)
        else:
            raise JsonError("invalid JSON value for google.protobuf.Value")
        return True
    if name in _WRAPPERS:
        field = _field(message, "value")
        message._set_field(
            field,
            _parse_value(field.codec, value, ignore_unknown=ignore_unknown_fields),
        )
        return True
    if name == "google.protobuf.Any":
        if not isinstance(value, Mapping):
            raise JsonError("Any requires a JSON object")
        if not value:
            return True
        try:
            type_url = value["@type"]
        except KeyError as error:
            raise JsonError("@type is required for Any") from error
        if not isinstance(type_url, str):
            raise JsonError("Any @type must be a string")
        registry = message.__class__.__REGISTRY__
        if registry is None:
            raise JsonError("Any ProtoJSON requires a namespace registry")
        try:
            embedded_type = registry.message_class(registry.type_name(type_url))
        except (LookupError, TypeError, ValueError) as error:
            raise JsonError(str(error)) from error
        embedded = embedded_type()
        if embedded.__PROTO_FULL_NAME__ in _ANY_VALUE_TYPES:
            if "value" not in value:
                raise JsonError("value is required for an Any containing a WKT")
            parse_value(
                value["value"],
                embedded,
                ignore_unknown_fields=ignore_unknown_fields,
            )
        else:
            parse_dict(
                {key: item for key, item in value.items() if key != "@type"},
                embedded,
                ignore_unknown_fields=ignore_unknown_fields,
            )
        _set(message, "type_url", type_url)
        _set(message, "value", embedded.SerializeToString(deterministic=True))
        return True
    if name == "google.protobuf.Empty":
        if not isinstance(value, Mapping):
            raise JsonError("Empty requires a JSON object")
        if value and not ignore_unknown_fields:
            raise JsonError(f"unknown field {next(iter(value))!r}")
        return True
    return False


def parse_value(
    data: Any,
    message: M,
    *,
    ignore_unknown_fields: bool = False,
) -> M:
    """Replace a direct message from its ProtoJSON value."""
    message.Clear()
    with message._suspend_mutation(), message._suspend_reset_mask():
        if _parse_well_known(
            data, message, ignore_unknown_fields=ignore_unknown_fields
        ):
            return message
    if not isinstance(data, Mapping):
        raise JsonError("message ProtoJSON must be an object")
    return parse_dict(data, message, ignore_unknown_fields=ignore_unknown_fields)


def parse_dict(
    data: Mapping[str, Any],
    message: M,
    *,
    ignore_unknown_fields: bool = False,
) -> M:
    """Replace a direct message from a ProtoJSON-compatible dictionary."""
    message.Clear()
    names: dict[str, Field] = {}
    for declared in message.__FIELDS__:
        if not declared.public:
            continue
        names[declared.proto_name] = declared
        names[_json_name(declared)] = declared
    seen: set[Field] = set()
    seen_oneofs: set[str] = set()
    with message._suspend_mutation(), message._suspend_reset_mask():
        for name, raw in data.items():
            field = names.get(name)
            if field is None:
                extension = _extension_for_json_name(message, name)
                if extension is not None:
                    _parse_extension(message, extension, raw, ignore_unknown_fields)
                    continue
                if ignore_unknown_fields:
                    continue
                raise JsonError(f"unknown field {name!r}")
            if raw is None and not _accepts_null(field.codec):
                message._clear_state(field)
                seen.add(field)
                continue
            if field.oneof is not None:
                if field.oneof in seen_oneofs:
                    raise JsonError(
                        f"multiple fields supplied for oneof {field.oneof!r}"
                    )
                seen_oneofs.add(field.oneof)
            if field.map:
                if not isinstance(raw, Mapping):
                    raise JsonError("map field requires a JSON object")
                key_codec = cast(ValueCodec[Any], field.map_key_codec)
                parsed_map: dict[Any, Any] = {}
                for key, item in raw.items():
                    parsed = _parse_value(
                        field.codec,
                        item,
                        ignore_unknown=ignore_unknown_fields,
                    )
                    if parsed is not _SKIP:
                        parsed_map[_parse_map_key(key_codec, key)] = parsed
                message._set_field(field, parsed_map)
            elif field.repeated:
                if not isinstance(raw, list):
                    raise JsonError("repeated field requires a JSON array")
                if any(item is None for item in raw) and not _accepts_null(field.codec):
                    raise JsonError("repeated fields do not accept null elements")
                parsed_items = [
                    _parse_value(
                        field.codec,
                        item,
                        ignore_unknown=ignore_unknown_fields,
                    )
                    for item in raw
                ]
                message._set_field(
                    field, [item for item in parsed_items if item is not _SKIP]
                )
            else:
                parsed = _parse_value(
                    field.codec, raw, ignore_unknown=ignore_unknown_fields
                )
                if parsed is not _SKIP:
                    if field in seen and field.message:
                        current = message._values.get(field)
                        if current is None:
                            message._set_field(field, parsed)
                        else:
                            cast(Message, current).MergeFrom(cast(Message, parsed))
                    else:
                        message._set_field(field, parsed)
            seen.add(field)
    return message


def _extension_for_json_name(message: Message, name: str) -> Extension[Any] | None:
    registry = message.__class__.__EXTENSION_REGISTRY__
    if registry is None or not (name.startswith("[") and name.endswith("]")):
        return None
    extension = registry.by_name(name[1:-1])
    return extension if extension is not None and extension.public else None


def _parse_extension(
    message: Message,
    extension: Extension[Any],
    raw: Any,
    ignore_unknown_fields: bool,
) -> None:
    if raw is None and not _accepts_null(extension.value_codec):
        message.clear_extension(extension)
        return
    if extension.repeated:
        if not isinstance(raw, list) or (
            any(item is None for item in raw)
            and not _accepts_null(extension.value_codec)
        ):
            raise JsonError("repeated extension requires a non-null JSON array")
        parsed_values = [
            _parse_value(
                extension.value_codec,
                item,
                ignore_unknown=ignore_unknown_fields,
            )
            for item in raw
        ]
        value = [item for item in parsed_values if item is not _SKIP]
    else:
        value = _parse_value(
            extension.value_codec, raw, ignore_unknown=ignore_unknown_fields
        )
        if value is _SKIP:
            return
    message.set_extension(extension, value)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise JsonError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise JsonError(f"invalid JSON constant {value!r}")


def message_from_json(
    payload: str | bytes | bytearray,
    message: M,
    *,
    ignore_unknown_fields: bool = False,
) -> M:
    """Replace a direct message from a ProtoJSON document."""
    try:
        data = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except JsonError:
        raise
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise JsonError(str(error)) from error
    return parse_value(data, message, ignore_unknown_fields=ignore_unknown_fields)


def message_to_json(
    message: Message,
    *,
    preserving_proto_field_name: bool = False,
    always_print_fields_with_no_presence: bool = False,
    use_integers_for_enums: bool = False,
    indent: int | None = 2,
    sort_keys: bool = False,
) -> str:
    """Serialize a direct message to a ProtoJSON document."""
    return json.dumps(
        message_to_value(
            message,
            preserving_proto_field_name=preserving_proto_field_name,
            always_print_fields_with_no_presence=always_print_fields_with_no_presence,
            use_integers_for_enums=use_integers_for_enums,
        ),
        ensure_ascii=False,
        indent=indent,
        sort_keys=sort_keys,
    )
