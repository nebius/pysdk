"""Handle Nebius SDK options for gRPC channels.

This module supplies functions that extract and validate options from gRPC
channel arguments. It also supplies constants for common Nebius options.

The options configure channel security and compression.
"""

from collections.abc import Sequence
from typing import Any, TypeVar

from grpc.aio._typing import ChannelArgumentType

T = TypeVar("T")


class WrongTypeError(Exception):
    """Exception raised when an option has an unexpected type.

    This exception is raised by the option extraction functions when an
    option value does not match the expected type.

    :param name: The name of the option that had the wrong type.
    :param exp_type: The expected type for the option value.
    :param received: The actual value received.
    """

    def __init__(self, name: str, exp_type: type[T], received: Any) -> None:
        super().__init__(
            f"Option with name {name} expected type is {type(exp_type)},"
            f" found {type(received)}"
        )


def pop_option(
    args: ChannelArgumentType,
    name: str,
    expected_type: type[T],
) -> tuple[ChannelArgumentType, T | None]:
    """Extract the last occurrence of a named option from channel arguments.

    Search the channel arguments for the name and validate matching values.
    Return the remaining arguments and the last match. Return ``None`` if
    there is no match.

    :param args: The channel arguments to search.
    :param name: The name of the option to extract.
    :param expected_type: The expected type of the option value.
    :returns: A tuple of (remaining_args, option_value), where option_value
        is the last matching value or None.
    :raises WrongTypeError: If an option with the name has a wrong type.
    """
    ret, found = pop_options(args, name, expected_type)
    return ret, found[-1] if len(found) > 0 else None


def pop_options(
    args: ChannelArgumentType,
    name: str,
    expected_type: type[T],
) -> tuple[ChannelArgumentType, Sequence[T]]:
    """Extract all occurrences of a named option from channel arguments.

    Search the channel arguments for the name and validate matching values.
    Return the remaining arguments and all matches.

    :param args: The channel arguments to search.
    :param name: The name of the option to extract.
    :param expected_type: The expected type of the option values.
    :returns: A tuple of (remaining_args, option_values), where option_values
        is a sequence of matching values.
    :raises WrongTypeError: If any option with the name has a wrong type.
    """
    ret = list[tuple[str, Any]]()
    found = list[T]()
    for arg in args:
        if arg[0] == name:
            if isinstance(arg[1], expected_type):
                found.append(arg[1])
            else:
                raise WrongTypeError(name, expected_type, arg[1])
        else:
            ret.append(arg)
    return ret, found


INSECURE = "nebius.insecure"
"""Option name for insecure channel configuration"""
COMPRESSION = "nebius.compression"
"""Option name for compression settings"""
