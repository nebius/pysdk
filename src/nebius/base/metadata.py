"""Metadata helpers for gRPC-style key/value headers."""

from collections.abc import Iterable, MutableSequence, Sequence
from typing import overload


class Authorization:
    """Namespace for authorization-related metadata constants."""

    DISABLE = "disable"


class Metadata(MutableSequence[tuple[str, str]]):
    """Mutable metadata collection with case-insensitive keys.

    This container normalizes keys to lowercase and supports convenient
    indexing by integer, slice, or key string:

    - ``metadata[i]`` returns the key/value tuple at index ``i``.
    - ``metadata[i:j]`` returns a list of key/value tuples.
    - ``metadata["key"]`` returns a list of values for that key.
    """

    def __init__(self, initial: Iterable[tuple[str, str]] | None = None) -> None:
        """Create a metadata collection.

        :param initial: Optional iterable of ``(key, value)`` pairs. Only string
            keys and values are stored and keys are lowercased.
        """
        self._contents = list[tuple[str, str]]()
        if initial is not None:
            for k, v in initial:
                if isinstance(k, str) and isinstance(v, str):  # type: ignore[unused-ignore]
                    self._contents.append((k.lower(), v))

    def insert(self, index: int, value: tuple[str, str]) -> None:
        """Insert a key/value pair at the given index.

        :param index: Position at which to insert the entry.
        :param value: ``(key, value)`` tuple to insert; key is lowercased.
        """
        self._contents.insert(index, (value[0].lower(), value[1]))

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
        """Return the first or last value for a key.

        :param index: Metadata key to search.
        :param default: Value returned when the key is missing.
        :param first: When true return the first value instead of the last.
        :returns: The selected value or ``default`` when absent.
        """
        try:
            return self[index][0 if first else -1]
        except IndexError:
            return default

    def add(
        self,
        index: str,
        value: str,
    ) -> None:
        """Append a key/value pair, lowercasing the key.

        :param index: Metadata key to append.
        :param value: Metadata value to append.
        """
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
        """Return metadata entries by index, slice, or key."""
        if isinstance(index, int) or isinstance(index, slice):
            return self._contents[index]
        if isinstance(index, str):  # type: ignore[unused-ignore]
            index = index.lower()
            return [v for k, v in self._contents if k == index]
        raise TypeError("Index must be int, str or slice")

    def __has__(self, key: str) -> bool:
        """Return True if a key exists in the collection."""
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
        """Set metadata by numeric index, slice, or key."""
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
        """Delete metadata by numeric index, slice, or key."""
        if isinstance(index, int) or isinstance(index, slice):
            del self._contents[index]
            return
        if isinstance(index, str):  # type: ignore[unused-ignore]
            index = index.lower()
            self._contents = [v for v in self._contents if v[0] != index]
            return
        raise TypeError("Index must be int, str or slice")

    def __repr__(self) -> str:
        """Return a debug representation of the metadata."""
        return f"{self.__class__.__name__}{list(self)}"

    def __len__(self) -> int:
        """Return the number of stored entries."""
        return len(self._contents)
