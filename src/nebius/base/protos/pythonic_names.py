"""Utilities for deriving Python-friendly names from protobuf identifiers."""

import re
from keyword import iskeyword, issoftkeyword
from logging import getLogger

pep8_const_re = re.compile(r"^_?[A-Z][A-Z0-9_]*$")
pep8_class_re = re.compile(r"^_?[A-Z][a-zA-Z0-9_]*$")
pep8_method_re = re.compile(r"^_?[a-z][a-z0-9_]*$")
pep8_attr_re = re.compile(r"^_?[a-z][a-z0-9_]*$")

logger = getLogger(__name__)


class NameError(Exception):
    """Raised when a name cannot be converted into a valid Python identifier."""

    pass


def first_non_underscore(s: str) -> str:
    """Return the first non-underscore character or an empty string.

    :param s: Input string.
    :returns: First non-underscore character or ``""``.
    """
    for char in s:
        if char != "_":
            return char
    return ""


def is_reserved_name(s: str) -> bool:
    """Return True if ``s`` is a Python keyword or soft keyword.

    :param s: Name to test.
    :returns: ``True`` if reserved.
    """
    return iskeyword(s) or issoftkeyword(s)


def _modify_name(
    suggested_name: str,
    container_name: str,
    *,
    lower: bool = True,
    full_proto_name: str = "",
) -> str:
    """Adjust a proposed name to avoid reserved words and conflicts.

    :param suggested_name: Initial candidate name.
    :param container_name: Enclosing scope name used for conflict prefixes.
    :param lower: Whether to lower the prefix letter.
    :param full_proto_name: Fully qualified proto name for warnings.
    :returns: Adjusted name.
    """
    # get first container name letter
    first_container_letter = first_non_underscore(container_name)
    if first_container_letter == "":
        first_container_letter = "x"
    if lower:
        first_container_letter = first_container_letter.lower()
    else:
        first_container_letter = first_container_letter.upper()

    # if suggested name is reserved or conflicts with getter, prefix it
    if is_reserved_name(suggested_name):
        ret = f"{first_container_letter}_{suggested_name}"
        logger.warning(
            f"Suggested name '{suggested_name}' for {full_proto_name} is reserved in"
            " Python and cannot be "
            f"used. Prefixing with first container letter {first_container_letter}."
            f" Resulting name: '{ret}'."
        )
        return ret

    # Check keywords conflict pattern
    # We have to do it regardless of actual conflict because it has to be always
    # deterministic and the name has to stay the same
    conflict_with_reserved_words = rf"^({first_container_letter}+)_(.*)$"
    match1 = re.match(conflict_with_reserved_words, suggested_name)
    if match1:
        prefix, something = match1.groups()
        if is_reserved_name(something):
            # Add another letter to the sequence
            ret = f"{prefix + first_container_letter}_{something}"
            logger.warning(
                f"Suggested name '{suggested_name}' for {full_proto_name} potentially"
                " conflicts with other"
                f" units renamed from a reserved word '{something}'."
                f" Prefixing with repeated first container letter "
                f"{first_container_letter}. Resulting name: '{ret}'."
            )
            return ret

    # Check magic conflict pattern
    # As in previous check, we have to check for both the original and the potentially
    # modified names, because we don't want conflicts
    conflict_with_magic_methods = rf"^_({first_container_letter}*)_(.*)__$"
    match2 = re.match(conflict_with_magic_methods, suggested_name)
    if match2:
        prefix, something = match2.groups()
        # Add another letter to the sequence
        ret = f"_{prefix + first_container_letter}_{something}__"
        logger.warning(
            f"Suggested name '{suggested_name}' for {full_proto_name} potentially "
            "conflicts with Python magic"
            f" methods '{something}' or units renamed from them."
            f" Prefixing with repeated first container letter {first_container_letter}."
            f" Resulting name: '{ret}'."
        )
        return ret

    # If no pattern matches, return the original string
    return suggested_name


def _class_name(full_name: str, annotated_name: str = "") -> str:
    """Resolve a Python class name from a protobuf full name.

    :param full_name: Fully qualified proto name.
    :param annotated_name: Optional explicit name from annotations.
    :returns: Valid Python class name.
    :raises NameError: If the annotated name is invalid.
    """
    if annotated_name != "":
        if is_reserved_name(annotated_name):
            raise NameError(
                f"Class name '{annotated_name}' is reserved in Python and cannot be "
                "used."
            )
        if re.match(r"^__.*__$", annotated_name):
            raise NameError(
                f"Class name '{annotated_name}' conflicts with Python magic methods."
            )
        if not pep8_class_re.match(annotated_name):
            raise NameError(
                f"Class name '{annotated_name}' is not a canonical Python class name."
            )
        if annotated_name.startswith("_"):
            raise NameError(
                f"Class name '{annotated_name}' should not start with an underscore."
            )
        return annotated_name
    name_parts = full_name.split(".")
    class_name = name_parts[-1]
    container_name = name_parts[-2] if len(name_parts) > 1 else ""
    return _modify_name(class_name, container_name, full_proto_name=full_name)


# canonical enum names are already pythonic, we have to only check for conflicts
def enum(
    full_enum_name: str, annotated_name: str = "", full_proto_name: str = ""
) -> str:
    """Return a Python enum name from a protobuf enum name.

    :param full_enum_name: Fully qualified proto enum name.
    :param annotated_name: Optional explicit name from annotations.
    :param full_proto_name: Fully qualified proto name for warnings.
    :returns: Valid Python enum class name.
    :raises NameError: If the annotated name is invalid.
    """
    return _class_name(full_enum_name, annotated_name=annotated_name)


# canonical message names are already pythonic, we have to only check for conflicts
def message(full_enum_name: str, annotated_name: str = "") -> str:
    """Return a Python message name from a protobuf message name.

    :param full_enum_name: Fully qualified proto message name.
    :param annotated_name: Optional explicit name from annotations.
    :returns: Valid Python message class name.
    :raises NameError: If the annotated name is invalid.
    """
    return _class_name(full_enum_name, annotated_name=annotated_name)


# canonical one-of names are already pythonic, we have to only check for conflicts
def one_of(
    field_name: str,
    message_name: str,
    annotated_name: str = "",
    full_proto_name: str = "",
) -> str:
    """Return a Python attribute name for a oneof declaration.

    :param field_name: Oneof field name.
    :param message_name: Containing message name.
    :param annotated_name: Optional explicit name from annotations.
    :param full_proto_name: Fully qualified proto name for warnings.
    :returns: Valid Python attribute name.
    :raises NameError: If the annotated name is invalid.
    """
    if annotated_name != "":
        if is_reserved_name(annotated_name):
            raise NameError(
                f"OneOf name '{annotated_name}' is reserved in Python and cannot be"
                " used."
            )
        if re.match(r"^__.*__$", annotated_name):
            raise NameError(
                f"OneOf name '{annotated_name}' conflicts with Python magic methods."
            )
        if not pep8_attr_re.match(annotated_name):
            raise NameError(
                f"OneOf name '{annotated_name}' is not a canonical Python attribute"
                " name."
            )
        if annotated_name.startswith("_"):
            raise NameError(
                f"OneOf name '{annotated_name}' should not start with an underscore."
            )
        return annotated_name
    return _modify_name(field_name, message_name, full_proto_name=full_proto_name)


def service(full_service_name: str, annotated_name: str = "") -> str:
    """Return a Python service class name from a protobuf service name.

    :param full_service_name: Fully qualified proto service name.
    :param annotated_name: Optional explicit name from annotations.
    :returns: Valid Python service class name.
    :raises NameError: If the annotated name is invalid.
    """
    return _class_name(full_service_name, annotated_name)


# canonical field names are already pythonic, we have to only check for conflicts
def field(
    field_name: str,
    message_name: str,
    annotated_name: str = "",
    full_proto_name: str = "",
) -> str:
    """Return a Python attribute name for a message field.

    :param field_name: Field name in proto.
    :param message_name: Containing message name.
    :param annotated_name: Optional explicit name from annotations.
    :param full_proto_name: Fully qualified proto name for warnings.
    :returns: Valid Python attribute name.
    :raises NameError: If the annotated name is invalid.
    """
    if annotated_name != "":
        if is_reserved_name(annotated_name):
            raise NameError(
                f"Field name '{annotated_name}' is reserved in Python and cannot be"
                " used."
            )
        if re.match(r"^__.*__$", annotated_name):
            raise NameError(
                f"Field name '{annotated_name}' conflicts with Python magic methods."
            )
        if not pep8_attr_re.match(annotated_name):
            raise NameError(
                f"Field name '{annotated_name}' is not a canonical Python attribute"
                " name."
            )
        if annotated_name.startswith("_"):
            raise NameError(
                f"Field name '{annotated_name}' should not start with an underscore."
            )
        return annotated_name
    return _modify_name(field_name, message_name, full_proto_name=full_proto_name)


# canonical enum value names are already pythonic, we have to only check for conflicts
def enum_value(
    value_name: str, enum_name: str, annotated_name: str = "", full_proto_name: str = ""
) -> str:
    """Return a Python constant name for an enum value.

    :param value_name: Enum value name in proto.
    :param enum_name: Containing enum name.
    :param annotated_name: Optional explicit name from annotations.
    :param full_proto_name: Fully qualified proto name for warnings.
    :returns: Valid Python constant name.
    :raises NameError: If the annotated name is invalid.
    """
    if annotated_name != "":
        if is_reserved_name(annotated_name):
            raise NameError(
                f"Enum value name '{annotated_name}' is reserved in Python and cannot "
                "be used."
            )
        if re.match(r"^__.*__$", annotated_name):
            raise NameError(
                f"Enum value name '{annotated_name}' conflicts with Python magic "
                "methods."
            )
        if not pep8_const_re.match(annotated_name):
            raise NameError(
                f"Enum value name '{annotated_name}' is not a canonical Python constant"
                " name."
            )
        if annotated_name.startswith("_"):
            raise NameError(
                f"Enum value name '{annotated_name}' should not start with an"
                " underscore."
            )
        return annotated_name
    return _modify_name(
        value_name, enum_name, lower=False, full_proto_name=full_proto_name
    )


def pascal_to_snake_case(name: str) -> str:
    """Convert a PascalCase string to snake_case.

    This conversion preserves leading underscores and splits abbreviations.

    :param name: PascalCase name.
    :returns: snake_case representation.
    """
    has_underscore = name[0] == "_"
    # Step 1: Separate PascalCase components
    name = re.sub(r"(_+)", r"_\1", name)
    name = re.sub(r"(?<=[A-Z])([A-Z][a-z])", r"_\1", name)
    name = re.sub(r"(?<=_)([a-z])", r"_\1", name)
    name = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)

    if not has_underscore and name[0] == "_":
        name = name[1:]
    # Step 3: Convert to lowercase
    return name.lower()


# convert all pascal methods to snake case
def method(
    method_name: str,
    service_name: str,
    annotated_name: str = "",
    full_proto_name: str = "",
) -> str:
    """Return a Python method name for a service method.

    :param method_name: Proto method name.
    :param service_name: Containing service name.
    :param annotated_name: Optional explicit name from annotations.
    :param full_proto_name: Fully qualified proto name for warnings.
    :returns: Valid Python method name.
    :raises NameError: If the annotated name is invalid.
    """
    if annotated_name != "":
        if is_reserved_name(annotated_name):
            raise NameError(
                f"Method name '{annotated_name}' is reserved in Python and cannot be"
                " used."
            )
        if re.match(r"^__.*__$", annotated_name):
            raise NameError(
                f"Method name '{annotated_name}' conflicts with Python magic methods."
            )
        if not pep8_method_re.match(annotated_name):
            raise NameError(
                f"Method name '{annotated_name}' is not a canonical Python method name."
            )
        if annotated_name.startswith("_"):
            raise NameError(
                f"Method name '{annotated_name}' should not start with an underscore."
            )
        return annotated_name
    return _modify_name(
        pascal_to_snake_case(method_name), service_name, full_proto_name=full_proto_name
    )
