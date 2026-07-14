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


pattern = re.compile(
    r"^(?P<leading>[./])?"
    r"(?P<service>[\w_]+(?:\.[\w_]+)*)"
    r"(?P<separator>[./])"
    r"(?P<method>[\w_]+)$"
)
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
    match = pattern.fullmatch(input_string)
    if not match:
        raise InvalidMethodNameError(f"The method name {input_string} is malformed.")

    leading = match.group("leading")
    separator = match.group("separator")
    if leading and separator != leading:
        raise InvalidMethodNameError(
            f"Delimiter {separator} does not match the initial delimiter {leading}."
        )
    return match.group("service")
