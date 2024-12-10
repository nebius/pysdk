from collections.abc import Sequence
from typing import Any, TypeVar

from grpc.aio._typing import ChannelArgumentType

T = TypeVar("T")


class WrongTypeError(Exception):
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
    ret, found = pop_options(args, name, expected_type)
    return ret, found[-1] if len(found) > 0 else None


def pop_options(
    args: ChannelArgumentType,
    name: str,
    expected_type: type[T],
) -> tuple[ChannelArgumentType, Sequence[T]]:
    ret = list[tuple[str, Any]]()
    found = list[T]()
    for arg in args:
        if arg[0] == name:
            if isinstance(arg[1], expected_type):
                found.append(arg[1])
            else:
                WrongTypeError(name, expected_type, arg[1])
        else:
            ret.append(arg)
    return ret, found


INSECURE = "nebius.insecure"
COMPRESSION = "nebius.compression"
