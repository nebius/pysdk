from typing import Any, Type

from google.protobuf.descriptor import Descriptor, FileDescriptor
from google.protobuf.message import Message as PMessage

from nebius.base.protos.pb_enum import Enum  # type:ignore[attr-defined,unused-ignore]

from .descriptor import DescriptorWrap


class Message:
    def __init__(
        self,
        initial_message: PMessage | None,
        class_var: Type[PMessage],
        full_name: str,
        descriptor: FileDescriptor,
    ):
        if isinstance(initial_message, class_var):
            setattr(self, "__#base__", initial_message)
        elif initial_message is not None:
            AttributeError(
                f"Wrong initial message type: expected {class_var.__name__},"
                f" received {type(initial_message)}."
            )
        else:
            setattr(self, "__#base__", class_var())
        setattr(self, "__#class__", class_var)
        setattr(self, "__#full_name__", full_name)
        setattr(
            self,
            "__#descriptor__",
            DescriptorWrap[Descriptor](full_name, descriptor, Descriptor),
        )

    def get_descriptor(self) -> Descriptor:
        msg_name = getattr(self, "__#full_name__")
        desc: Any = getattr(self, "__#descriptor__", None)
        if desc is None:
            raise ValueError(f"Descriptor not set for message {msg_name}.")
        if isinstance(desc, DescriptorWrap):
            desc = desc()
            setattr(self, "__#descriptor__", desc)
        if isinstance(desc, Descriptor):
            return desc
        raise ValueError(f"Descriptor not found for message {msg_name}.")

    def check_presence(self, name: str) -> bool:
        base = getattr(self, "__#base__")  # type: ignore[unused-ignore]
        return base.HasField(name)  # type: ignore[unused-ignore,no-any-return]

    def _clear_field(
        self,
        name: str,
    ) -> None:
        base = getattr(self, "__#base__")  # type: ignore[unused-ignore]
        return base.ClearField(name)  # type: ignore

    def _get_field(
        self,
        name: str,
        explicit_presence: bool = False,
        wrap: Any = None,
    ) -> Any:
        base = getattr(self, "__#base__")  # type: ignore[unused-ignore]
        if explicit_presence and not base.HasField(name):  # type: ignore[unused-ignore]
            return None
        ret = getattr(base, name)
        if isinstance(wrap, type(Enum)):
            return wrap.__new__(wrap, ret)
        if wrap is not None:
            return wrap(ret)
        return ret

    def _set_field(
        self,
        name: str,
        value: Any,
        explicit_presence: bool = False,
    ) -> None:
        base = getattr(self, "__#base__")  # type: ignore[unused-ignore]
        base.ClearField(name)  # type: ignore[unused-ignore]
        if explicit_presence and value is None:
            return

        if isinstance(value, Message):
            value = getattr(value, "__#base__")
        if isinstance(value, PMessage):
            sub_msg = getattr(base, name)
            if not isinstance(sub_msg, PMessage):
                msg_name = getattr(self, "__#full_name__")
                raise AttributeError(
                    f"Attribute {name} of message {msg_name} is not a message."
                )
            sub_msg.MergeFrom(value)
            return
        return setattr(base, name, value)
