from typing import Any, final


class Singleton(type):
    _instances = dict[Any, Any]()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


@final
class UnsetType(metaclass=Singleton):
    def __repr__(self) -> str:
        return __name__ + ".Unset"


Unset = UnsetType()
