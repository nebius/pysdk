from typing import Any, final


class Singleton(type):
    """A metaclass that creates a singleton class."""

    _instances = dict[Any, Any]()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


@final
class UnsetType(metaclass=Singleton):
    """Used to represent an unset optional parameter."""

    def __repr__(self) -> str:
        return __name__ + ".Unset"


Unset = UnsetType()
"""Used to represent an unset optional parameter."""
