"""Singleton sentinel representing an unset optional parameter."""

from typing import Any, final


class Singleton(type):
    """A metaclass that creates a singleton class."""

    _instances = dict[Any, Any]()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Return the singleton instance for the class."""
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


@final
class UnsetType(metaclass=Singleton):
    """Used to represent an unset optional parameter."""

    def __repr__(self) -> str:
        """Return a readable sentinel representation."""
        return __name__ + ".Unset"


Unset = UnsetType()
"""Singleton sentinel representing an unset optional parameter."""
