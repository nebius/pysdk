"""Owned mutable containers used by direct protobuf messages."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, MutableMapping
from typing import Generic, TypeVar, cast, overload

from .codec import ValueCodec

K = TypeVar("K")
V = TypeVar("V")
D = TypeVar("D")


class MapValues(MutableMapping[K, V], Generic[K, V]):
    """Stable protobuf map with validated keys and owned values."""

    def __init__(
        self,
        key_codec: ValueCodec[K],
        value_codec: ValueCodec[V],
        on_mutation: Callable[[], None],
    ) -> None:
        self._key_codec = key_codec
        self._value_codec = value_codec
        self._on_mutation = on_mutation
        self._items: dict[K, V] = {}

    def _key(self, key: object) -> K:
        return self._key_codec.normalize(key)

    def _prepare(self, value: object) -> V:
        owned = self._value_codec.copy(self._value_codec.normalize(value))
        if self._value_codec.bind_mutation is not None:
            self._value_codec.bind_mutation(owned, self._on_mutation)
        return owned

    def _default(self) -> V:
        value = self._value_codec.default()
        if self._value_codec.bind_mutation is not None:
            self._value_codec.bind_mutation(value, self._on_mutation)
        return value

    def _detach(self, value: V) -> None:
        if self._value_codec.bind_mutation is not None:
            self._value_codec.bind_mutation(value, lambda: None)

    def __getitem__(self, key: K) -> V:
        normalized = self._key(key)
        if normalized not in self._items:
            self._items[normalized] = self._default()
            self._on_mutation()
        return self._items[normalized]

    def __contains__(self, key: object) -> bool:
        return self._key(key) in self._items

    @overload
    def get(self, key: K) -> V | None: ...

    @overload
    def get(self, key: K, default: V) -> V: ...

    @overload
    def get(self, key: K, default: D) -> V | D: ...

    def get(self, key: K, default: D | None = None) -> V | D | None:
        """Return a value without protobuf map auto-vivification."""
        return self._items.get(self._key(key), default)

    def setdefault(self, key: K, default: V | None = None) -> V:
        if self._value_codec.bind_mutation is not None:
            raise NotImplementedError("setting a message map default is unsupported")
        if default is None:
            raise ValueError("scalar map setdefault requires a non-None default")
        normalized = self._key(key)
        if normalized in self._items:
            return self._items[normalized]
        self[normalized] = default
        return self._items[normalized]

    def __setitem__(self, key: K, value: V) -> None:
        normalized_key = self._key(key)
        prepared = self._prepare(value)
        previous = self._items.get(normalized_key)
        if previous is not None:
            self._detach(previous)
        self._items[normalized_key] = prepared
        self._on_mutation()

    def __delitem__(self, key: K) -> None:
        normalized = self._key(key)
        value = self._items[normalized]
        self._detach(value)
        del self._items[normalized]
        self._on_mutation()

    def __iter__(self) -> Iterator[K]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        if self._items:
            for value in self._items.values():
                self._detach(value)
            self._items.clear()
            self._on_mutation()

    def replace(self, values: Mapping[K, V]) -> None:
        prepared = {
            self._key(key): self._prepare(value) for key, value in values.items()
        }
        for value in self._items.values():
            self._detach(value)
        self._items = prepared
        self._on_mutation()

    def set_owned(self, key: object, value: object) -> None:
        """Replace one decoded entry using normal ownership rules."""
        self[cast(K, key)] = cast(V, value)

    def __repr__(self) -> str:
        return repr(self._items)
