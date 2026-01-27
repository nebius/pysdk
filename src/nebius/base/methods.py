"""Helpers for parsing and normalizing gRPC-style method identifiers."""

import re

from nebius.base.error import SDKError


def fix_name(method_name: str) -> str:
    """Normalize a fully-qualified gRPC method name to dotted form.

    gRPC method names are commonly expressed as ``/package.Service/Method``.
    This helper strips the leading slash and replaces remaining slashes with
    dots, yielding ``package.Service.Method``. If the name is already in a
    non-slashed format it is returned unchanged.

    :param method_name: Method name to normalize.
    :returns: Dotted method identifier.
    """
    if method_name[0] != "/":
        return method_name
    method_name = method_name[1:]
    return method_name.replace("/", ".")


class InvalidMethodNameError(SDKError):
    """Raised when a method name does not match expected patterns."""


pattern = r"([\./]?)([\w_]+(?:\.[\w_]+)*)(?:(\1|[\./]))([\w_]+)"
"""Regular expression used to parse service and method components."""


def service_from_method_name(input_string: str) -> str:
    """Extract the service name portion from a method identifier.

    Accepts gRPC-style method names separated by either ``/`` or ``.`` and
    returns the service portion. For example, both ``/pkg.Service/Method`` and
    ``pkg.Service.Method`` yield ``pkg.Service``.

    :param input_string: Method name to parse.
    :raises InvalidMethodNameError: If the name is malformed or the delimiter
        usage is inconsistent.
    :returns: Service identifier portion of the method name.
    """
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
