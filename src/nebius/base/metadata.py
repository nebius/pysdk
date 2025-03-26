from collections.abc import Iterable, MutableSequence, Sequence
from typing import overload


class Internal:
    """
    Metadata tags for internal usage, that will be filtered out.

    All the tags must be prefixed with `PREFIX`, by which they will be filtered.
    The PREFIX is constructed such that if it leaks into the actual GRPC, it will cause
    an error.
    """

    PREFIX = ":NebiusInternal:\r\n"

    AUTHORIZATION = PREFIX + "authorization"
    AUTHORIZATION_OPTION = PREFIX + "authorization_option"


class Authorization:
    DISABLE = "disable"


class Metadata(MutableSequence[tuple[str, str]]):
    def __init__(self, initial: Iterable[tuple[str, str]] | None = None) -> None:
        self._contents = list[tuple[str, str]]()
        if initial is not None:
            for k, v in initial:
                if isinstance(k, str) and isinstance(v, str):  # type: ignore[unused-ignore]
                    self._contents.append((k.lower(), v))

    def insert(self, index: int, value: tuple[str, str]) -> None:
        self._contents.insert(index, (value[0].lower(), value[1]))

    def clean(self) -> "Metadata":
        return Metadata([v for v in self if v[0].startswith(Internal.PREFIX.lower())])

    @overload
    def get_one(
        self,
        index: str,
        default: str,
        first: bool = False,
    ) -> str: ...

    @overload
    def get_one(
        self,
        index: str,
        default: None = None,
        first: bool = False,
    ) -> str | None: ...

    def get_one(
        self,
        index: str,
        default: str | None = None,
        first: bool = False,
    ) -> str | None:
        try:
            return self[index][0 if first else -1]
        except IndexError:
            return default

    def add(
        self,
        index: str,
        value: str,
    ) -> None:
        self._contents.append((index.lower(), value))

    @overload
    def __getitem__(self, index: int) -> tuple[str, str]: ...

    @overload
    def __getitem__(self, index: slice) -> MutableSequence[tuple[str, str]]: ...

    @overload
    def __getitem__(self, index: str) -> Sequence[str]: ...

    def __getitem__(
        self, index: int | slice | str
    ) -> tuple[str, str] | MutableSequence[tuple[str, str]] | Sequence[str]:
        if isinstance(index, int) or isinstance(index, slice):
            return self._contents[index]
        if isinstance(index, str):  # type: ignore[unused-ignore]
            index = index.lower()
            return [v for k, v in self._contents if k == index]
        raise TypeError("Index must be int, str or slice")

    def __has__(self, key: str) -> bool:
        key = key.lower()
        for k, _ in self._contents:
            if k == key:
                return True
        return False

    def __setitem__(
        self,
        index: int | slice | str,
        value: tuple[str, str] | Iterable[tuple[str, str]] | Iterable[str] | str,
    ) -> None:
        if isinstance(index, int):
            if (
                isinstance(value, tuple)
                and len(value) == 2
                and isinstance(value[0], str)
                and isinstance(value[1], str)
            ):
                self._contents[index] = (value[0].lower(), value[1])
                return
            else:
                TypeError("If index is int, value must be Tuple[str,str]")
        if isinstance(index, slice):
            for i, v in zip(range(len(self))[index], value):  # type: ignore[unused-ignore]
                self[i] = v
            return
        if isinstance(index, str):  # type: ignore[unused-ignore]
            index = index.lower()
            del self[index]
            if isinstance(value, str):
                value = [value]
            for s in value:
                if isinstance(s, str):
                    self.append((index, s))
                else:
                    raise TypeError(
                        "If index is str, value must be str or Iterable[str]"
                    )
            return
        raise TypeError("Index must be int, str or slice")

    def __delitem__(self, index: int | slice | str) -> None:
        if isinstance(index, int) or isinstance(index, slice):
            del self._contents[index]
            return
        if isinstance(index, str):  # type: ignore[unused-ignore]
            index = index.lower()
            self._contents = [v for v in self._contents if v[0] != index]
            return
        raise TypeError("Index must be int, str or slice")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}{list(self)}"

    def __len__(self) -> int:
        return len(self._contents)
