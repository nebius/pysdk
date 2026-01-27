"""Utilities for handling gRPC channel options specific to Nebius SDK.

This module provides functions to extract and validate options from gRPC
channel arguments, as well as constants for common Nebius-specific options.

The options are used to configure various aspects of the gRPC channels,
such as security settings and compression.
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

    This function searches for options with the given name in the channel
    arguments, validates their type, and returns the remaining arguments
    along with the last matching option value (or None if not found).

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

    This function searches for all options with the given name in the channel
    arguments, validates their types, and returns the remaining arguments
    along with a sequence of matching option values.

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
