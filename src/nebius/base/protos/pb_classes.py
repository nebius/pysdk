from collections.abc import (
    Callable,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    MutableSequence,
)
from typing import (
    Any,
    TypeVar,
    overload,
)

from google.protobuf.descriptor import Descriptor
from google.protobuf.message import Message as PMessage

from nebius.base.error import SDKError

from .descriptor import DescriptorWrap
from .pb_enum import Enum

T = TypeVar("T")
R = TypeVar("R")


def wrap_type(obj: T, wrap: Callable[[T], R] | None = None) -> R | T:
    # if isinstance(wrap, type(Enum)):
    #     return wrap.__new__(wrap, obj)
    if wrap is not None:
        return wrap(obj)
    return obj


def unwrap_type(obj: Any, unwrap: Callable[[Any], Any] | None = None) -> Any:
    if isinstance(obj, Message):
        return obj.__pb2_message__  # type: ignore[unused-ignore]
    if isinstance(obj, Mapping):
        return {k: unwrap_type(v, unwrap) for k, v in obj.items()}  # type: ignore[unused-ignore]
    if (
        isinstance(obj, Iterable)
        and not isinstance(obj, str)
        and not isinstance(obj, bytes)
    ):
        return [unwrap_type(x, unwrap) for x in obj]  # type: ignore[unused-ignore]
    if unwrap is not None:
        return unwrap(obj)
    return obj


class OneOf:
    name: str


class OneOfMatchError(SDKError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unexpected oneof field name {name} returned.")


class Message:
    __PB2_CLASS__: type[PMessage]
    __PB2_DESCRIPTOR__: DescriptorWrap[Descriptor] | Descriptor

    def __init__(self, initial_message: PMessage | None):
        if not hasattr(self, "__PB2_CLASS__"):
            raise AttributeError(
                f"Proto Class not set for message {self.__class__.__name__}"
            )
        if isinstance(initial_message, self.__PB2_CLASS__):  # type: ignore[unused-ignore]
            self.__pb2_message__ = initial_message
        elif initial_message is not None:
            AttributeError(
                f"Wrong initial message type: expected {self.__PB2_CLASS__},"  # type: ignore[unused-ignore]
                f" received {type(initial_message)}."
            )
        else:
            self.__pb2_message__ = self.__PB2_CLASS__()  # type: ignore[unused-ignore]

    @classmethod
    def get_descriptor(cls) -> Descriptor:
        if not hasattr(cls, "__PB2_DESCRIPTOR__") or cls.__PB2_DESCRIPTOR__ is None:  # type: ignore[unused-ignore]
            raise ValueError(f"Descriptor not set for message {cls.__name__}.")
        if isinstance(cls.__PB2_DESCRIPTOR__, DescriptorWrap):  # type: ignore[unused-ignore]
            cls.__PB2_DESCRIPTOR__ = cls.__PB2_DESCRIPTOR__()
        if isinstance(cls.__PB2_DESCRIPTOR__, Descriptor):  # type: ignore[unused-ignore]
            return cls.__PB2_DESCRIPTOR__
        raise ValueError(f"Descriptor not found for message {cls.__name__}.")

    def check_presence(self, name: str) -> bool:
        return self.__pb2_message__.HasField(name)  # type: ignore[unused-ignore,no-any-return]

    def which_field_in_oneof(self, name: str) -> str | None:
        return self.__pb2_message__.WhichOneof(name)  # type: ignore[no-any-return]

    def _clear_field(
        self,
        name: str,
    ) -> None:
        return self.__pb2_message__.ClearField(name)  # type: ignore[unused-ignore]

    def _get_field(
        self,
        name: str,
        explicit_presence: bool = False,
        wrap: Callable[[Any], Any] | None = None,
    ) -> Any:
        if explicit_presence and not self.__pb2_message__.HasField(name):  # type: ignore[unused-ignore]
            return None
        ret = getattr(self.__pb2_message__, name)  # type: ignore[unused-ignore]
        return wrap_type(ret, wrap)

    def _set_field(
        self,
        name: str,
        value: Any,
        unwrap: Callable[[Any], Any] | None = None,
        explicit_presence: bool = False,
    ) -> None:
        self.__pb2_message__.ClearField(name)  # type: ignore[unused-ignore]
        if explicit_presence and value is None:
            return

        value = unwrap_type(value, unwrap)
        if isinstance(value, Mapping):  # type: ignore[unused-ignore]
            pb_arr = getattr(self.__pb2_message__, name)  # type: ignore[unused-ignore]
            for k, v in value.items():  # type: ignore[unused-ignore]
                if isinstance(v, PMessage):  # type: ignore[unused-ignore]
                    pb_arr[k].MergeFrom(v)
                else:
                    pb_arr[k] = v
            return
        elif (
            isinstance(value, Iterable)
            and not isinstance(value, str)
            and not isinstance(value, bytes)
        ):
            pb_arr = getattr(self.__pb2_message__, name)  # type: ignore[unused-ignore]
            pb_arr.extend(value)
            return
        elif isinstance(value, PMessage):
            sub_msg = getattr(self.__pb2_message__, name)  # type: ignore[unused-ignore]
            if not isinstance(sub_msg, PMessage):
                raise AttributeError(
                    f"Attribute {name} of message {self.__class__.__name__} is not "
                    "a message."
                )
            sub_msg.MergeFrom(value)
            return
        return setattr(self.__pb2_message__, name, value)  # type: ignore[unused-ignore]


MapKey = TypeVar("MapKey", int, str, bool)
CollectibleInner = TypeVar("CollectibleInner", int, str, float, bytes, bool, PMessage)
CollectibleOuter = TypeVar(
    "CollectibleOuter", int, str, float, bytes, bool, Enum, Message, PMessage
)


class Repeated(MutableSequence[CollectibleOuter]):
    @classmethod
    def with_wrap(
        cls,
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
    ) -> Callable[
        [MutableSequence[CollectibleInner]],
        "Repeated[CollectibleOuter]",
    ]:
        def ret(
            source: MutableSequence[CollectibleInner],
        ) -> "Repeated[CollectibleOuter]":
            return cls(source, wrap=wrap, unwrap=unwrap)  # type: ignore

        return ret

    def __init__(
        self,
        source: MutableSequence[CollectibleInner],
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
    ):
        self._source = source  # type: ignore
        self._wrap = wrap  # type: ignore
        self._unwrap = unwrap  # type: ignore

    def insert(self, index: int, value: CollectibleOuter) -> None:
        if isinstance(value, Message):
            value = value.__pb2_message__  # type: ignore
        self._source.insert(index, value)  # type: ignore[unused-ignore]

    @overload
    def __getitem__(self, index: int) -> CollectibleOuter: ...
    @overload
    def __getitem__(self, index: slice) -> MutableSequence[CollectibleOuter]: ...
    def __getitem__(
        self, index: int | slice
    ) -> CollectibleOuter | MutableSequence[CollectibleOuter]:
        if isinstance(index, int):
            ret = self._source[index]
            return wrap_type(ret, self._wrap)  # type: ignore [unused-ignore]
        elif isinstance(index, slice):  # type: ignore [unused-ignore]
            return [wrap_type(ret, self._wrap) for ret in self._source[index]]  # type: ignore [unused-ignore]
        else:
            raise TypeError("Index must be int or slice")

    def __setitem__(
        self,
        index: int | slice,
        value: CollectibleOuter | Iterable[CollectibleOuter],
    ) -> None:
        if isinstance(index, int):
            value = unwrap_type(value, self._unwrap)
            if len(self._source) == index:
                self._source.append(value)  # type: ignore [unused-ignore]
                return
            if isinstance(value, PMessage):
                self._source[index].Clear()  # type: ignore [unused-ignore]
                self._source[index].MergeFrom(value)  # type: ignore [unused-ignore]
            else:
                self._source[index] = value  # type: ignore [unused-ignore]
        elif isinstance(index, slice):  # type: ignore [unused-ignore]
            for i, v in zip(range(len(self))[index], value):  # type: ignore[arg-type]
                self[i] = v  # type: ignore[assignment]

    def __delitem__(self, index: int | slice) -> None:
        self._source.__delitem__(index)

    def __len__(self) -> int:
        return len(self._source)


class Map(MutableMapping[MapKey, CollectibleOuter]):
    @classmethod
    def with_wrap(
        cls,
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
    ) -> Callable[
        [MutableMapping[MapKey, CollectibleInner]],
        "Map[MapKey, CollectibleOuter]",
    ]:
        def ret(
            source: MutableMapping[MapKey, CollectibleInner],
        ) -> "Map[MapKey, CollectibleOuter]":
            return cls(source, wrap=wrap, unwrap=unwrap)  # type: ignore[arg-type]

        return ret

    def __init__(
        self,
        source: MutableMapping[MapKey, CollectibleInner],
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
    ):
        self._source: MutableMapping[MapKey, CollectibleInner] = source  # type: ignore[assignment]
        self._wrap: Callable[[CollectibleInner], CollectibleOuter] = wrap  # type: ignore[assignment]
        self._unwrap: Callable[[CollectibleOuter], CollectibleInner] = unwrap  # type: ignore[assignment]

    def __getitem__(self, key: MapKey) -> CollectibleOuter:
        ret = self._source[key]  # type: ignore[assignment,unused-ignore]
        return wrap_type(ret, self._wrap)  # type: ignore[unused-ignore,arg-type]

    def __setitem__(self, key: MapKey, value: CollectibleOuter) -> None:
        value = unwrap_type(value, self._unwrap)  # type: ignore[unused-ignore]
        if isinstance(value, PMessage):
            self._source[key].Clear()  # type: ignore[unused-ignore]
            self._source[key].MergeFrom(value)  # type: ignore[unused-ignore]
        else:
            self._source[key] = value  # type: ignore

    def __delitem__(self, key: MapKey) -> None:
        self._source.__delitem__(key)  # type: ignore[unused-ignore]

    def __iter__(self) -> Iterator[MapKey]:
        return self._source.__iter__()  # type: ignore[unused-ignore]

    def __len__(self) -> int:
        return len(self._source)  # type: ignore[unused-ignore]
