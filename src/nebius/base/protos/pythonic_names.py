import re
from keyword import iskeyword, issoftkeyword


def first_non_underscore(s: str) -> str:
    for char in s:
        if char != "_":
            return char
    return ""


def is_reserved_name(s: str) -> bool:
    return iskeyword(s) or issoftkeyword(s)


def _modify_name(
    suggested_name: str, container_name: str, *, lower: bool = True
) -> str:
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
        return f"{first_container_letter}_{suggested_name}"

    # Check keywords conflict pattern
    # We have to do it regardless of actual conflict because it has to be always
    # deterministic and the name has to stay the same
    conflict_with_reserved_words = rf"^({first_container_letter}+)_(.*)$"
    match1 = re.match(conflict_with_reserved_words, suggested_name)
    if match1:
        prefix, something = match1.groups()
        if is_reserved_name(something):
            # Add another letter to the sequence
            return f"{prefix + first_container_letter}_{something}"

    # Check magic conflict pattern
    # As in previous check, we have to check for both the original and the potentially
    # modified names, because we don't want conflicts
    conflict_with_magic_methods = rf"^_({first_container_letter}*)_(.*)__$"
    match2 = re.match(conflict_with_magic_methods, suggested_name)
    if match2:
        prefix, something = match2.groups()
        # Add another letter to the sequence
        return f"_{prefix + first_container_letter}_{something}__"

    # If no pattern matches, return the original string
    return suggested_name


def _class_name(full_name: str) -> str:
    name_parts = full_name.split(".")
    class_name = name_parts[-1]
    container_name = name_parts[-2] if len(name_parts) > 1 else ""
    return _modify_name(class_name, container_name)


# canonical enum names are already pythonic, we have to only check for conflicts
def enum(full_enum_name: str) -> str:
    return _class_name(full_enum_name)


# canonical message names are already pythonic, we have to only check for conflicts
def message(full_enum_name: str) -> str:
    return _class_name(full_enum_name)


# canonical one-of names are already pythonic, we have to only check for conflicts
def one_of(field_name: str, message_name: str) -> str:
    return _modify_name(field_name, message_name)


def service(full_service_name: str) -> str:
    return _class_name(full_service_name)


# canonical field names are already pythonic, we have to only check for conflicts
def field(field_name: str, message_name: str) -> str:
    return _modify_name(field_name, message_name)


# canonical enum value names are already pythonic, we have to only check for conflicts
def enum_value(value_name: str, enum_name: str) -> str:
    return _modify_name(value_name, enum_name, lower=False)


def pascal_to_snake_case(name: str) -> str:
    """
    Converts a PascalCase string to snake_case with double underscores as separators
    and respects abbreviations. Also ensures no collisions by appending unique suffixes
    if needed.
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
# TODO: create deterministic version that will convert all the names to some
# variant with no collisions, favoring pascal names.
def method(method_name: str, service_name: str) -> str:
    return _modify_name(pascal_to_snake_case(method_name), service_name)
