import re

from nebius.base.error import SDKError


def fix_name(method_name: str) -> str:
    if method_name[0] != "/":
        return method_name
    method_name = method_name[1:]
    return method_name.replace("/", ".")


class InvalidMethodNameError(SDKError):
    pass


pattern = r"([\./]?)([\w_]+(?:\.[\w_]+)*)(?:(\1|[\./]))([\w_]+)"


def service_from_method_name(input_string: str) -> str:
    match = re.match(pattern, input_string)
    if not match:
        raise InvalidMethodNameError(f"The method name {input_string} is malformed.")

    group1 = match.group(1)  # Delimiter (optional)
    group2 = match.group(2)  # First part of the name
    group3 = match.group(3)  # Delimiter or fallback
    group4 = match.group(4)  # Second part of the name

    # Validate group2 and group4
    if not group2:
        raise InvalidMethodNameError("Method name has to include service name.")
    if not group4:
        raise InvalidMethodNameError("Method name has to include method.")

    # Validate group3 consistency with group1 if group1 is found
    if group1 and group3 != group1:
        raise InvalidMethodNameError(
            f"Delimiter {group3} does not match the initial delimiter {group1}."
        )
    return group2
