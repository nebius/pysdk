from collections.abc import Iterable, Mapping
from json import dumps, loads
from re import compile
from typing import overload

_simple_string_pattern = compile("^[a-zA-Z0-9_]+$")


class Error(Exception):
    pass


class MarshalError(Error):
    pass


class FieldKey(str):
    @classmethod
    def unmarshal(cls, marshaled_key: str) -> "FieldKey":
        if marshaled_key.startswith('"'):
            return cls(loads(marshaled_key))
        if _simple_string_pattern.match(marshaled_key):
            return cls(marshaled_key)
        raise MarshalError("malformed FieldKey string")

    def marshal(self) -> str:
        if _simple_string_pattern.match(self):
            return str(self)
        else:
            return dumps(str(self))


class FieldPath(list[FieldKey]):
    @overload
    def __init__(self) -> None: ...

    @overload
    def __init__(self, base: Iterable[FieldKey | str]) -> None: ...

    def __init__(self, base: Iterable[FieldKey | str] | None) -> None:  # type: ignore
        super().__init__()
        if base is not None:
            if not isinstance(base, Iterable):  # type: ignore[unused-ignore]
                raise ValueError(f"base should be iterable, got {type(base)}")
            for v in base:
                if isinstance(v, str):  # type: ignore[unused-ignore]
                    v = FieldKey(v)
                if not isinstance(v, FieldKey):  # type: ignore[unused-ignore]
                    raise ValueError(
                        "base contents should be FieldKey or str, got " f"{type(v)}"
                    )
                self.append(v)

    def parent(self) -> "FieldPath|None":
        if len(self) == 0:
            return None
        return FieldPath(self[:-1].copy())

    def copy(self) -> "FieldPath":
        return FieldPath(super().copy())

    def to_mask(self) -> "Mask":
        ret = Mask()
        cur = ret
        for v in self:
            nxt = Mask()
            cur.field_parts[v] = nxt
            cur = nxt
        return ret

    @staticmethod
    def _matches_reset_mask(
        fp: "FieldPath|list[FieldKey]", mask: "Mask|None"
    ) -> tuple[bool, bool]:
        if not isinstance(mask, Mask):
            return False, False
        if len(fp) == 0:
            return True, mask.is_empty()
        key, rest = fp[0], fp[1:]
        has_match = False
        is_final = False
        if mask.any is not None:
            has_match, is_final = FieldPath._matches_reset_mask(rest, mask.any)
        if key in mask.field_parts:
            k_match, k_final = FieldPath._matches_reset_mask(
                rest, mask.field_parts[key]
            )
            has_match |= k_match
            if k_match:
                is_final |= k_final
        return has_match, is_final

    @staticmethod
    def _matches_select_mask(
        fp: "FieldPath|list[FieldKey]", mask: "Mask|None"
    ) -> tuple[bool, bool]:
        if mask is None or mask.is_empty():
            return True, len(fp) != 0
        if len(fp) == 0:
            return True, False
        key, rest = fp[0], fp[1:]
        has_match = False
        is_inner = False
        if mask.any is not None:
            has_match, is_inner = FieldPath._matches_select_mask(rest, mask.any)
        if key in mask.field_parts:
            k_match, k_final = FieldPath._matches_select_mask(
                rest, mask.field_parts[key]
            )
            has_match |= k_match
            if k_match:
                is_inner |= k_final
        return has_match, is_inner

    def matches_reset_mask(self, mask: "Mask|None") -> bool:
        ret, _ = FieldPath._matches_reset_mask(self, mask)
        return ret

    def matches_reset_mask_final(self, mask: "Mask|None") -> bool:
        ret, fin = FieldPath._matches_reset_mask(self, mask)
        return ret and fin

    def matches_select_mask(self, mask: "Mask|None") -> bool:
        ret, _ = FieldPath._matches_select_mask(self, mask)
        return ret

    def matches_select_mask_inner(self, mask: "Mask|None") -> tuple[bool, bool]:
        return FieldPath._matches_select_mask(self, mask)

    def marshal(self) -> str:
        return self.to_mask().marshal()

    def __repr__(self) -> str:
        try:
            return f"FieldPath({self.marshal()})"
        except Exception as e:
            return f"FieldPath(not-marshalable {e})"

    @classmethod
    def unmarshal(cls, s: str) -> "FieldPath|None":
        return Mask.unmarshal(s).to_field_path()

    def __iadd__(self, value: "Iterable[FieldKey|str]") -> "FieldPath":  # type: ignore[misc,override]
        for v in value:
            if isinstance(v, str):  # type: ignore[unused-ignore]
                v = FieldKey(v)
            if not isinstance(v, FieldKey):  # type: ignore[unused-ignore]
                raise ValueError(
                    "value contents should be FieldKey or str, got " f"{type(v)}"
                )
            self.append(v)
        return self

    @overload  # type: ignore[override]
    def __add__(self, value: Iterable[FieldKey | str]) -> "FieldPath": ...

    @overload
    def __add__(self, value: "Mask") -> "Mask": ...

    def __add__(self, other: "Iterable[FieldKey|str]|Mask") -> "FieldPath|Mask":  # type: ignore[unused-ignore]
        if isinstance(other, Mask):
            mask = Mask()
            cur = mask
            for i, v in enumerate(self):
                nxt = Mask()
                if i == len(self) - 1:
                    nxt = other
                cur.field_parts[v] = nxt
                cur = nxt
            return mask
        cp = self.copy()
        cp += other
        return cp

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, FieldPath):
            return False
        return super().__eq__(value)

    def is_prefix_of(self, value: "FieldPath") -> bool:
        if not isinstance(value, FieldPath):  # type: ignore[unused-ignore]
            return False
        if len(self) >= len(value):
            return False
        for i, v in enumerate(self):
            if value[i] != v:
                return False
        return True


class Mask:
    def __init__(
        self,
        any: "Mask|None" = None,
        field_parts: Mapping[FieldKey | str, "Mask"] | None = None,
    ) -> None:
        if any is not None and not isinstance(any, Mask):  # type: ignore[unused-ignore]
            raise ValueError(f"any should be Map or None, got {type(any)}")
        self.any: "Mask|None" = any
        self.field_parts = dict[FieldKey, "Mask"]()
        if isinstance(field_parts, Mapping):
            for k, v in field_parts.items():
                if isinstance(k, str):  # type: ignore[unused-ignore]
                    k = FieldKey(k)
                if not isinstance(k, FieldKey):  # type: ignore[unused-ignore]
                    raise ValueError(
                        "field_parts keys should be FieldKey or str, got" f" {type(k)}"
                    )
                if not isinstance(v, Mask):  # type: ignore[unused-ignore]
                    raise ValueError(
                        "field_parts values should be of type Mask, " f"got {type(v)}"
                    )
                self.field_parts[k] = v

    def is_empty(self) -> bool:
        return (self.any is None) and len(self.field_parts) == 0

    def to_field_path(self) -> FieldPath | None:
        if self.any is not None:
            raise Error("wildcard in the mask")
        if len(self.field_parts) > 1:
            raise Error("multiple paths in the mask")
        for k, v in self.field_parts.items():
            inner = v.to_field_path()
            if inner is None:
                return FieldPath([k])
            return FieldPath([k]) + inner
        return None

    def is_field_path(self) -> bool:
        try:
            self.to_field_path()
        except Error:
            return False
        return True

    def __iadd__(self, other: "Mask|FieldPath|None") -> "Mask":
        if isinstance(other, FieldPath):
            other = other.to_mask()
        if other is None or other.is_empty():
            return self
        if self.any is not None:
            self.any += other.any
        elif other.any is not None:
            self.any = other.any.copy()
        for k, v in other.field_parts.items():
            if k in self.field_parts:
                self.field_parts[k] += v
            else:
                self.field_parts[k] = v.copy()
        return self

    def __add__(self, other: "Mask|FieldPath|None") -> "Mask":
        cp = self.copy()
        cp += other
        return cp

    def copy(self) -> "Mask":
        ret = Mask()
        if self.any is not None:
            ret.any = self.any.copy()
        for k, v in self.field_parts.items():
            ret.field_parts[k] = v.copy()
        return ret

    def sub_mask(self, path: FieldPath | FieldKey) -> "Mask|None":
        if isinstance(path, FieldKey):
            if path in self.field_parts:
                if self.any is not None:
                    ret: Mask | None = self.field_parts[path].copy()
                    if ret is None:
                        return ret
                    ret += self.any
                    return ret
                return self.field_parts[path]
            return self.any
        if isinstance(path, FieldPath):  # type: ignore[unused-ignore]
            ret = self
            for s in path:
                if ret is None:
                    return None
                ret = ret.sub_mask(s)
            return ret
        raise Error(f"unexpected path type {type(path)}")

    def __repr__(self) -> str:
        try:
            return f"Mask({self.marshal()})"
        except RecursionError:
            return "Mask(not-marshalable <too deep>)"
        except Exception as e:
            return f"Mask(not-marshalable {e})"

    def __eq__(self, value: object) -> bool:
        try:
            if not isinstance(value, Mask):
                return False
            if self.any != value.any:
                return False
            if len(self.field_parts) != len(value.field_parts):
                return False
            for k, v in self.field_parts.items():
                if k not in value.field_parts or value.field_parts[k] != v:
                    return False
        except RecursionError:
            return False
        return True

    def _marshal(self) -> tuple[int, str]:
        if self.is_empty():
            return 0, ""
        ret = list[str]()

        def append_to_ret(key: str, mask: "Mask") -> None:
            counter, mask_str = mask._marshal()
            if mask_str == "":
                ret.append(key)
            elif counter == 1:
                ret.append(key + "." + mask_str)
            else:
                ret.append(key + ".(" + mask_str + ")")

        if self.any is not None:
            append_to_ret("*", self.any)
        for k, v in self.field_parts.items():
            append_to_ret(k.marshal(), v)
        ret = sorted(ret)
        return len(ret), ",".join(ret)

    def marshal(self) -> str:
        return self._marshal()[1]

    def intersect_reset_mask(self, other: "Mask|None") -> "Mask|None":
        ret = Mask()
        if not isinstance(other, Mask):
            return None
        if self.any is not None:
            ret.any = self.any.intersect_reset_mask(other.any)
            for k, v in other.field_parts.items():
                inner = self.any.intersect_reset_mask(v)
                if inner is not None:
                    ret.field_parts[k] = inner
        if other.any is not None:
            for k, v in self.field_parts.items():
                inner = other.any.intersect_reset_mask(v)
                if inner is not None:
                    if k in ret.field_parts:
                        ret.field_parts[k] += inner
                    else:
                        ret.field_parts[k] = inner
        for k, v in self.field_parts.items():
            if k in other.field_parts:
                inner = v.intersect_reset_mask(other.field_parts[k])
                if inner is not None:
                    if k in ret.field_parts:
                        ret.field_parts[k] += inner
                    else:
                        ret.field_parts[k] = inner
        return ret

    def __and__(self, other: "Mask|None") -> "Mask|None":
        return self.intersect_reset_mask(other)

    def intersect_dumb(self, other: "Mask|None") -> "Mask|None":
        if not isinstance(other, Mask):
            return None
        ret = Mask()
        if self.any is not None:
            ret.any = self.any.intersect_dumb(other.any)
        for k, v in self.field_parts.items():
            if k in other.field_parts:
                inner = v.intersect_dumb(other.field_parts[k])
                if inner is not None:
                    ret.field_parts[k] = inner
        return ret

    def __imul__(self, other: "Mask") -> "Mask":
        if not isinstance(other, Mask):  # type: ignore[unused-ignore]
            raise ValueError(f"argument 2 must be Mask, {type(other)} given")
        ret = self.intersect_dumb(other)
        if not isinstance(ret, Mask):  # type: ignore[unused-ignore]
            raise Error(f"return should have been Mask, got {type(ret)}")
        return ret

    def __mul__(self, other: "Mask") -> "Mask":
        cp = self.copy()
        cp *= other
        return cp

    def subtract_dumb(self, other: "Mask|None") -> None:
        if not isinstance(other, Mask):
            return
        if self.any is not None and other.any is not None:
            self.any.subtract_dumb(other.any)
            if self.any.is_empty():
                self.any = None
        for k in list(self.field_parts.keys()):
            if k in other.field_parts:
                self.field_parts[k].subtract_dumb(other.field_parts[k])
                if self.field_parts[k].is_empty():
                    del self.field_parts[k]

    def __itruediv__(self, other: "Mask") -> "Mask":
        if not isinstance(other, Mask):  # type: ignore[unused-ignore]
            raise ValueError(f"argument 2 must be Mask, {type(other)} given")
        self.subtract_dumb(other)
        return self

    def __truediv__(self, other: "Mask") -> "Mask":
        cp = self.copy()
        cp /= other
        return cp

    def subtract_reset_mask(self, other: "Mask|None") -> None:
        if not isinstance(other, Mask):
            return
        if self.any is not None:
            self.any.subtract_reset_mask(other.any)
            if self.any.is_empty():
                self.any = None
        for k in list(self.field_parts.keys()):
            if other.any is None and k not in other.field_parts:
                continue

            if other.any is not None:
                self.field_parts[k].subtract_reset_mask(other.any)
            if k in other.field_parts:
                self.field_parts[k].subtract_reset_mask(other.field_parts[k])
            if self.field_parts[k].is_empty():
                del self.field_parts[k]

    @classmethod
    def unmarshal(cls, source: str) -> "Mask":
        from .fieldmask_parser import parse

        return parse(source)

    def __isub__(self, other: "Mask|None") -> "Mask":
        self.subtract_reset_mask(other)
        return self

    def __sub__(self, other: "Mask|None") -> "Mask":
        cp = self.copy()
        cp -= other
        return cp
