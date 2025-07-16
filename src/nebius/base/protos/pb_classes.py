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

from nebius.aio.abc import ClientChannelInterface
from nebius.base.error import SDKError
from nebius.base.fieldmask import FieldKey, Mask
from nebius.base.token_sanitizer import TokenSanitizer

from .descriptor import DescriptorWrap
from .pb_enum import Enum

T = TypeVar("T")
R = TypeVar("R")


def simple_wrapper(
    wrap: Callable[[T], R],
) -> Callable[[str, ClientChannelInterface, T], R]:
    def wrapper(_: str, __: ClientChannelInterface, obj: T) -> R:
        return wrap(obj)

    return wrapper


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


def repr_field(key: str, attr: Any, indent: str = "") -> str:
    ret = ""
    el_repr = repr(attr).split("\n")
    if isinstance(attr, Message):
        ret += indent + key + " " + el_repr[0] + "\n"
        for line in el_repr[1:]:
            ret += indent + line + "\n"
    else:
        if len(el_repr) == 1:
            ret += indent + key + ": " + el_repr[0] + "\n"
        else:
            ret += indent + key + ": |\n"
            for line in el_repr:
                ret += indent + "  " + line + "\n"
    return ret


credentials_sanitizer = TokenSanitizer.credentials_sanitizer()


def has_method(obj: Any, method: str) -> bool:
    return hasattr(obj, method) and callable(getattr(obj, method))


MaskFunction = Callable[[Any], Mask]


class Message:
    __PB2_CLASS__: type[PMessage]
    __PB2_DESCRIPTOR__: DescriptorWrap[Descriptor] | Descriptor
    __PY_TO_PB2__: dict[str, str]
    __default: "Message|None" = None
    __sensitive_fields = dict[str, bool]()
    __credentials_fields = dict[str, bool]()
    __mask_functions__: dict[str, MaskFunction]

    def __init__(self, initial_message: PMessage | None):
        self.__recorded_reset_mask = Mask()
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

    def get_full_update_reset_mask(self) -> Mask:
        desc = self.__class__.get_descriptor()
        ret = Mask()
        for el_key in dir(self):
            el_pb2_key = self.__class__.__PY_TO_PB2__[el_key]
            m_key = FieldKey(el_pb2_key)
            try:
                _ = desc.fields_by_name[el_pb2_key]
            except KeyError:
                continue
            el = getattr(self, el_key)

            m_mask = Mask()
            if el_key in self.__class__.__mask_functions__:
                m_mask = self.__class__.__mask_functions__[el_key](el)
            elif (
                isinstance(el, Map)
                or isinstance(el, Repeated)
                or isinstance(el, Message)
            ):
                if isinstance(el, Message):
                    m_mask = Message.get_full_update_reset_mask(el)
                else:
                    m_mask = el.get_full_update_reset_mask()

            # empty mask is either already set, or not necessary here
            if not m_mask.is_empty() or Message.is_default(self, el_key):
                ret.field_parts[m_key] = m_mask
        return ret

    def set_mask(self, new_mask: Mask) -> None:
        self.__recorded_reset_mask = new_mask

    def get_mask(self) -> Mask:
        return self.__recorded_reset_mask

    @classmethod
    def is_sensitive(cls, field_name: str) -> bool:
        if field_name in cls.__sensitive_fields:
            return cls.__sensitive_fields[field_name]
        from google.protobuf.descriptor import FieldDescriptor

        from nebius.api.nebius import sensitive

        fn_pb2 = cls.__PY_TO_PB2__[field_name]
        desc = cls.get_descriptor()
        field_desc: FieldDescriptor = desc.fields_by_name[fn_pb2]
        try:
            is_sensitive = bool(field_desc.GetOptions().Extensions[sensitive])  # type: ignore
        except AttributeError:
            is_sensitive = False
        cls.__sensitive_fields[field_name] = is_sensitive
        return is_sensitive

    @classmethod
    def is_credentials(cls, field_name: str) -> bool:
        if field_name in cls.__credentials_fields:
            return cls.__credentials_fields[field_name]
        from google.protobuf.descriptor import FieldDescriptor

        from nebius.api.nebius import credentials

        fn_pb2 = cls.__PY_TO_PB2__[field_name]
        desc = cls.get_descriptor()
        field_desc: FieldDescriptor = desc.fields_by_name[fn_pb2]
        try:
            is_creds = bool(field_desc.GetOptions().Extensions[credentials])  # type: ignore
        except AttributeError:
            is_creds = False
        cls.__credentials_fields[field_name] = is_creds
        return is_creds

    def __repr__(self) -> str:
        ret = self.__class__.__name__ + ":\n"
        desc = self.__class__.get_descriptor()
        for el in dir(self):
            el_pb2 = self.__class__.__PY_TO_PB2__[el]
            try:
                _ = desc.fields_by_name[el_pb2]
            except KeyError:
                continue
            if not Message.is_default(self, el):
                if self.__class__.is_sensitive(el):
                    ret += "  " + el + ": **HIDDEN**\n"
                    continue
                el_attr = getattr(self, el)
                if self.__class__.is_credentials(el):
                    if not isinstance(el_attr, str):
                        el_attr = repr(el_attr)
                    if credentials_sanitizer.is_supported(el_attr):
                        el_attr = credentials_sanitizer.sanitize(el_attr)
                    else:
                        el_attr = "**HIDDEN**"
                ret += repr_field(el, el_attr, "  ")
        return ret[:-1]

    def is_default(self, pythonic_name: str) -> bool:
        if self.__class__.__default is None:
            self.__class__.__default = self.__class__(None)
        return getattr(self, pythonic_name) == getattr(  # type: ignore[no-any-return]
            self.__class__.__default, pythonic_name
        )

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
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        return self.__pb2_message__.HasField(el_pb2)  # type: ignore[unused-ignore,no-any-return]

    def which_field_in_oneof(self, pb2_name: str) -> str | None:
        return self.__pb2_message__.WhichOneof(pb2_name)  # type: ignore[no-any-return]

    def _clear_field(
        self,
        name: str,
    ) -> None:
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        fk = FieldKey(el_pb2)
        if fk not in self.__recorded_reset_mask.field_parts:
            self.__recorded_reset_mask.field_parts[fk] = Mask()
        return self.__pb2_message__.ClearField(el_pb2)  # type: ignore[unused-ignore]

    def _get_field(
        self,
        name: str,
        explicit_presence: bool = False,
        wrap: Callable[[Any], Any] | None = None,
    ) -> Any:
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        if explicit_presence and not self.__pb2_message__.HasField(el_pb2):  # type: ignore[unused-ignore]
            return None
        ret = getattr(self.__pb2_message__, el_pb2)  # type: ignore[unused-ignore]
        ret = wrap_type(ret, wrap)
        if has_method(ret, "set_mask"):
            el_key = FieldKey(el_pb2)
            if el_key not in self.__recorded_reset_mask.field_parts:
                self.__recorded_reset_mask.field_parts[el_key] = Mask()
            if isinstance(ret, Message):  # may be overwritten
                Message.set_mask(ret, self.__recorded_reset_mask.field_parts[el_key])
            else:
                ret.set_mask(self.__recorded_reset_mask.field_parts[el_key])
        return ret

    def _set_field(
        self,
        name: str,
        value: Any,
        unwrap: Callable[[Any], Any] | None = None,
        explicit_presence: bool = False,
    ) -> None:
        el_pb2 = self.__class__.__PY_TO_PB2__[name]
        self.__pb2_message__.ClearField(el_pb2)  # type: ignore[unused-ignore]
        fk = FieldKey(el_pb2)
        if value is None:
            if fk not in self.__recorded_reset_mask.field_parts:
                self.__recorded_reset_mask.field_parts[fk] = Mask()
            return

        value = unwrap_type(value, unwrap)

        if self.__class__.__default is None:
            self.__class__.__default = self.__class__(None)
        if (
            not explicit_presence
            and getattr(self.__class__.__default.__pb2_message__, el_pb2) == value
        ):
            if fk not in self.__recorded_reset_mask.field_parts:
                self.__recorded_reset_mask.field_parts[fk] = Mask()

        if isinstance(value, Mapping):  # type: ignore[unused-ignore]
            pb_arr = getattr(self.__pb2_message__, el_pb2)  # type: ignore[unused-ignore]
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
            pb_arr = getattr(self.__pb2_message__, el_pb2)  # type: ignore[unused-ignore]
            pb_arr.extend(value)
            return
        elif isinstance(value, PMessage):
            sub_msg = getattr(self.__pb2_message__, el_pb2)  # type: ignore[unused-ignore]
            if not isinstance(sub_msg, PMessage):
                raise AttributeError(
                    f"Attribute {name} of message {self.__class__.__name__} is not "
                    "a message."
                )
            sub_msg.MergeFrom(value)
            return
        return setattr(self.__pb2_message__, el_pb2, value)  # type: ignore[unused-ignore]


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
        mask_function: MaskFunction | None = None,
    ) -> Callable[
        [MutableSequence[CollectibleInner]],
        "Repeated[CollectibleOuter]",
    ]:
        def ret(
            source: MutableSequence[CollectibleInner],
        ) -> "Repeated[CollectibleOuter]":
            return cls(source, wrap=wrap, unwrap=unwrap, mask_function=mask_function)  # type: ignore

        return ret

    def __init__(
        self,
        source: MutableSequence[CollectibleInner],
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
        mask_function: MaskFunction | None = None,
    ):
        self._source = source  # type: ignore
        self._wrap = wrap  # type: ignore
        self._unwrap = unwrap  # type: ignore
        self._mask_function = mask_function

    def insert(self, index: int, value: CollectibleOuter) -> None:
        if isinstance(value, Message):
            value = value.__pb2_message__  # type: ignore
        self._source.insert(index, value)  # type: ignore[unused-ignore]

    def __repr__(self) -> str:
        if len(self) == 0:
            return " []"
        ret = ""
        for i in self:
            ret += repr_field("-", i)
        return ret

    def get_mask(self) -> Mask | None:
        if len(self) == 0:
            return Mask()
        return None

    def get_full_update_reset_mask(self) -> Mask:
        ret = Mask()
        if len(self) > 0:
            if isinstance(self[0], Message) or self._mask_function is not None:
                func = (
                    self._mask_function
                    if self._mask_function is not None
                    else Message.get_full_update_reset_mask
                )
                ret.any = Mask()
                for el in self:
                    ret.any += func(el)  # type: ignore
        else:
            ret.any = Mask()
        return ret

    @overload
    def __getitem__(self, index: int) -> CollectibleOuter: ...

    @overload
    def __getitem__(self, index: slice) -> MutableSequence[CollectibleOuter]: ...

    def __getitem__(
        self, index: int | slice
    ) -> CollectibleOuter | MutableSequence[CollectibleOuter]:
        if isinstance(index, int):
            ret = self._source[index]
            return wrap_type(ret, self._wrap)  # type: ignore [unused-ignore,no-any-return]
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
        mask_function: MaskFunction | None = None,
    ) -> Callable[
        [MutableMapping[MapKey, CollectibleInner]],
        "Map[MapKey, CollectibleOuter]",
    ]:
        def ret(
            source: MutableMapping[MapKey, CollectibleInner],
        ) -> "Map[MapKey, CollectibleOuter]":
            return cls(source, wrap=wrap, unwrap=unwrap, mask_function=mask_function)  # type: ignore[arg-type]

        return ret

    def get_full_update_reset_mask(self) -> Mask:
        ret = Mask()
        if len(self) > 0:
            for _, el in self.items():
                if not isinstance(el, Message) and self._mask_function is None:
                    return Mask()
                if self._mask_function is None:
                    m_mask = Message.get_full_update_reset_mask(el)  # type: ignore
                else:
                    m_mask = self._mask_function(el)
                if not m_mask.is_empty():
                    if ret.any is None:
                        ret.any = Mask()
                    ret.any += m_mask
        else:
            ret.any = Mask()
        return ret

    def __init__(
        self,
        source: MutableMapping[MapKey, CollectibleInner],
        wrap: Callable[[CollectibleInner], CollectibleOuter] | None = None,
        unwrap: Callable[[CollectibleOuter], CollectibleInner] | None = None,
        mask_function: MaskFunction | None = None,
    ):
        self._source: MutableMapping[MapKey, CollectibleInner] = source  # type: ignore[assignment]
        self._wrap: Callable[[CollectibleInner], CollectibleOuter] = wrap  # type: ignore[assignment]
        self._unwrap: Callable[[CollectibleOuter], CollectibleInner] = unwrap  # type: ignore[assignment]
        self._mask_function = mask_function

    def __repr__(self) -> str:
        if len(self) == 0:
            return " {}"
        ret = ""
        for k, v in self.items():
            ret += repr_field(repr(k), v)
        return ret

    def __getitem__(self, key: MapKey) -> CollectibleOuter:
        ret = self._source[key]  # type: ignore[assignment,unused-ignore]
        return wrap_type(ret, self._wrap)  # type: ignore[unused-ignore,arg-type,return-value]

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
