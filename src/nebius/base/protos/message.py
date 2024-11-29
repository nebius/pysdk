from typing import Any, Type

from google.protobuf.message import Message as PMessage


class Message:
    def __init__(
        self,
        initial_message: PMessage | None,
        base_name: str,
        class_var: Type[PMessage],
    ):
        if isinstance(initial_message, class_var):
            setattr(self, base_name, initial_message)
        else:
            setattr(self, base_name, class_var())
        setattr(self, "#base_name", base_name)
        setattr(self, "#class", class_var)

    def check_presence(self, name: str) -> bool:
        return self._check_presence(name)

    def _check_presence(
        self,
        name: str,
        base: PMessage | None = None,
        base_name: str | None = None,
    ) -> bool:
        if base is None:
            if base_name is None:
                base_name = getattr(self, "#base_name")
            base = getattr(self, base_name)  # type: ignore[unused-ignore]
        return base.HasField(name)  # type: ignore[unused-ignore,no-any-return]

    def _clear_field(
        self, name: str, base: PMessage | None = None, base_name: str | None = None
    ) -> None:
        if base is None:
            if base_name is None:
                base_name = getattr(self, "#base_name")
            base = getattr(self, base_name)  # type: ignore[unused-ignore]
        return base.ClearField(name)  # type: ignore

    def _get_field(
        self,
        name: str,
        base: PMessage | None = None,
        base_name: str | None = None,
        explicit_presence: bool = False,
        wrap: Any = None,
    ) -> Any:
        if base is None:
            if base_name is None:
                base_name = getattr(self, "#base_name")
            base = getattr(self, base_name)  # type: ignore[unused-ignore]
        if explicit_presence and not base.HasField(name):  # type: ignore[unused-ignore]
            return None
        ret = getattr(base, name)
        if wrap is not None:
            return wrap(ret)
        return ret

    def _set_field(
        self,
        name: str,
        value: Any,
        base: PMessage | None = None,
        base_name: str | None = None,
        explicit_presence: bool = False,
    ) -> None:
        if base is None:
            if base_name is None:
                base_name = getattr(self, "#base_name")
            base = getattr(self, base_name)  # type: ignore[unused-ignore]
        if explicit_presence and value is None:
            base.ClearField(name)  # type: ignore[unused-ignore]

        if isinstance(value, Message):
            value = getattr(value, getattr(value, "#base_name"))
        return setattr(base, name, value)
