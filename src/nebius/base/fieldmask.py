"""Field mask utilities for partial updates and reset masks.

This module provides small, composable helpers for building, merging, and
serializing field masks used by the Nebius API. Masks are represented as a tree
of fields and can be serialized into the dotted syntax accepted by gRPC
metadata (for example, via the ``X-ResetMask`` header).

Basic usage
-----------

Create a simple mask by hand and serialize it::

    from nebius.base.fieldmask import FieldPath, Mask

    path = FieldPath(["spec", "max_size_bytes"])
    mask = path.to_mask()
    serialized = mask.marshal()
    # serialized == "spec.max_size_bytes"

Merge masks::

    mask = FieldPath(["spec", "max_size_bytes"]).to_mask()
    mask += FieldPath(["spec", "versioning"]).to_mask()
    # mask.marshal() == "spec.max_size_bytes,spec.versioning"

Use in request metadata (reset a field to its default)::

    from nebius.base.metadata import Metadata

    md = Metadata()
    md["X-ResetMask"] = "spec.max_size_bytes"
    # ... pass md into a request as metadata

Notes
-----

- The internal mask format supports wildcards and nesting. Not all masks are
  representable as a single field path.
- Masks are more granular than standard Google field masks and are not
  directly compatible.
"""

from collections.abc import Iterable, Mapping
from json import dumps, loads
from re import compile
from typing import overload

_simple_string_pattern = compile("^[a-zA-Z0-9_]+$")


class Error(Exception):
    """Base error for field mask operations."""

    pass


class MarshalError(Error):
    """Raised when parsing or serializing field mask strings fails."""

    pass


class FieldKey(str):
    """Field key component used in paths and mask trees."""

    @classmethod
    def unmarshal(cls, marshaled_key: str) -> "FieldKey":
        """Parse a single key from its marshaled representation.

        :param marshaled_key: Key string that may be quoted.
        :raises MarshalError: If the string is malformed.
        :returns: A :class:`FieldKey` instance.
        """
        if marshaled_key.startswith('"'):
            return cls(loads(marshaled_key))
        if _simple_string_pattern.match(marshaled_key):
            return cls(marshaled_key)
        raise MarshalError("malformed FieldKey string")

    def marshal(self) -> str:
        """Serialize the key, quoting if it contains special characters.

        :returns: Marshaled key string.
        """
        if _simple_string_pattern.match(self):
            return str(self)
        else:
            return dumps(str(self))


class FieldPath(list[FieldKey]):
    """Ordered path of :class:`FieldKey` components.

    Field paths are convenience objects that can be converted to masks and
    can be combined with other paths or masks using ``+``.

    :param base: Optional iterable of :class:`FieldKey` or strings used to build
        the path. Strings are converted to :class:`FieldKey` and validated.
    :raises ValueError: If ``base`` is not iterable or contains invalid element
        types.

    Example
    -------

    Construct a path and build a mask::

        path = FieldPath(["spec", "max_size_bytes"])
        mask = path.to_mask()
        assert mask.marshal() == "spec.max_size_bytes"
    """

    @overload
    def __init__(self) -> None: ...

    @overload
    def __init__(self, base: Iterable[FieldKey | str]) -> None: ...

    def __init__(self, base: Iterable[FieldKey | str] | None) -> None:  # type: ignore
        """Create a field path from keys or strings."""
        super().__init__()
        if base is not None:
            if not isinstance(base, Iterable):  # type: ignore[unused-ignore]
                raise ValueError(f"base should be iterable, got {type(base)}")
            for v in base:
                if isinstance(v, str):  # type: ignore[unused-ignore]
                    v = FieldKey(v)
                if not isinstance(v, FieldKey):  # type: ignore[unused-ignore]
                    raise ValueError(
                        f"base contents should be FieldKey or str, got {type(v)}"
                    )
                self.append(v)

    def parent(self) -> "FieldPath|None":
        """Return the parent path or ``None`` when at root.

        :returns: Parent path or ``None`` if this path is empty.
        """
        if len(self) == 0:
            return None
        return FieldPath(self[:-1].copy())

    def copy(self) -> "FieldPath":
        """Return a shallow copy of the path.

        :returns: New :class:`FieldPath` instance.
        """
        return FieldPath(super().copy())

    def to_mask(self) -> "Mask":
        """Convert the path into a mask with a single leaf.

        :returns: :class:`Mask` representing this path.
        """
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
        """Return True if the path is covered by a reset mask.

        :param mask: Mask to test against.
        :returns: ``True`` if the path is matched, otherwise ``False``.
        """
        ret, _ = FieldPath._matches_reset_mask(self, mask)
        return ret

    def matches_reset_mask_final(self, mask: "Mask|None") -> bool:
        """Return True if the path matches and terminates a reset mask.

        :param mask: Mask to test against.
        :returns: ``True`` if the path is matched and terminal.
        """
        ret, fin = FieldPath._matches_reset_mask(self, mask)
        return ret and fin

    def matches_select_mask(self, mask: "Mask|None") -> bool:
        """Return True if the path is covered by a select mask.

        :param mask: Mask to test against.
        :returns: ``True`` if the path is matched, otherwise ``False``.
        """
        ret, _ = FieldPath._matches_select_mask(self, mask)
        return ret

    def matches_select_mask_inner(self, mask: "Mask|None") -> tuple[bool, bool]:
        """Return match status and whether the match is inner or final.

        :param mask: Mask to test against.
        :returns: Tuple of ``(has_match, is_inner)``.
        """
        return FieldPath._matches_select_mask(self, mask)

    def marshal(self) -> str:
        """Serialize the path as a mask string.

        :returns: Marshaled mask string.
        """
        return self.to_mask().marshal()

    def __repr__(self) -> str:
        """Return a debug representation of the path."""
        try:
            return f"FieldPath({self.marshal()})"
        except Exception as e:
            return f"FieldPath(not-marshalable {e})"

    @classmethod
    def unmarshal(cls, s: str) -> "FieldPath|None":
        """Parse a single-path mask string into a :class:`FieldPath`.

        :param s: Marshaled mask string.
        :returns: A :class:`FieldPath` or ``None`` when the mask is empty.
        :raises Error: When the mask contains wildcards or multiple paths.
        """
        return Mask.unmarshal(s).to_field_path()

    def __iadd__(self, value: "Iterable[FieldKey|str]") -> "FieldPath":  # type: ignore[misc,override]
        """Append path components from an iterable.

        :param value: Iterable of :class:`FieldKey` or strings to append.
        :returns: This path instance.
        :raises ValueError: If an element is not a :class:`FieldKey` or string.
        """
        for v in value:
            if isinstance(v, str):  # type: ignore[unused-ignore]
                v = FieldKey(v)
            if not isinstance(v, FieldKey):  # type: ignore[unused-ignore]
                raise ValueError(
                    f"value contents should be FieldKey or str, got {type(v)}"
                )
            self.append(v)
        return self

    @overload  # type: ignore[override]
    def __add__(self, value: Iterable[FieldKey | str]) -> "FieldPath": ...

    @overload
    def __add__(self, value: "Mask") -> "Mask": ...

    def __add__(self, other: "Iterable[FieldKey|str]|Mask") -> "FieldPath|Mask":  # type: ignore[unused-ignore]
        """Combine with another path or attach a mask at the end.

        :param other: Iterable of keys to append or a :class:`Mask` to attach.
        :returns: A new :class:`FieldPath` or :class:`Mask`.
        """
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
        """Return True when another object is an equal path.

        :param value: Object to compare.
        :returns: ``True`` if equal, otherwise ``False``.
        """
        if not isinstance(value, FieldPath):
            return False
        return super().__eq__(value)

    def is_prefix_of(self, value: "FieldPath") -> bool:
        """Return True if this path is a strict prefix of another path.

        :param value: Path to compare with.
        :returns: ``True`` if this path is a strict prefix.
        """
        if not isinstance(value, FieldPath):  # type: ignore[unused-ignore]
            return False
        if len(self) >= len(value):
            return False
        for i, v in enumerate(self):
            if value[i] != v:
                return False
        return True


class Mask:
    """Tree representation of a field mask.

    A mask contains named field parts and an optional wildcard branch
    (``any``). Masks can be merged, intersected, or subtracted to build more
    complex partial update expressions.

    :param any: Wildcard sub-mask or ``None``.
    :param field_parts: Mapping of field names to nested masks.
    :raises ValueError: If inputs are not valid mask structures.

    :ivar any: Wildcard sub-mask or ``None``.
    :ivar field_parts: Mapping of field names to nested masks.

    Example
    -------

    Build a mask with a wildcard and a specific field::

        mask = Mask(any=FieldPath(["spec"]).to_mask())
        mask += FieldPath(["labels"]).to_mask()
        serialized = mask.marshal()
    """

    def __init__(
        self,
        any: "Mask|None" = None,
        field_parts: Mapping[FieldKey | str, "Mask"] | None = None,
    ) -> None:
        """Create a mask from an optional wildcard and field mapping."""
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
                        f"field_parts keys should be FieldKey or str, got {type(k)}"
                    )
                if not isinstance(v, Mask):  # type: ignore[unused-ignore]
                    raise ValueError(
                        f"field_parts values should be of type Mask, got {type(v)}"
                    )
                self.field_parts[k] = v

    def is_empty(self) -> bool:
        """Return True if the mask has no wildcard and no field parts.

        :returns: ``True`` if empty, otherwise ``False``.
        """
        return (self.any is None) and len(self.field_parts) == 0

    def to_field_path(self) -> FieldPath | None:
        """Convert a single-path mask to a :class:`FieldPath`.

        :returns: The field path or ``None`` when the mask is empty.
        :raises Error: If the mask uses wildcards or contains multiple paths.
        """
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
        """Return True if the mask can be represented as a single path.

        :returns: ``True`` if convertible to a :class:`FieldPath`.
        """
        try:
            self.to_field_path()
        except Error:
            return False
        return True

    def __iadd__(self, other: "Mask|FieldPath|None") -> "Mask":
        """Merge another mask or field path into this mask.

        :param other: Mask or path to merge in.
        :returns: This mask instance.
        """
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
        """Return a merged copy of this mask and another.

        :param other: Mask or path to merge in.
        :returns: New merged :class:`Mask`.
        """
        cp = self.copy()
        cp += other
        return cp

    def copy(self) -> "Mask":
        """Return a deep copy of the mask tree.

        :returns: New :class:`Mask` instance.
        """
        ret = Mask()
        if self.any is not None:
            ret.any = self.any.copy()
        for k, v in self.field_parts.items():
            ret.field_parts[k] = v.copy()
        return ret

    def sub_mask(self, path: FieldPath | FieldKey) -> "Mask|None":
        """Return a sub-mask for the provided field path or key.

        :param path: A :class:`FieldKey` or :class:`FieldPath`.
        :returns: The sub-mask, wildcard mask, or ``None`` if absent.
        """
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
        """Return a debug representation of the mask."""
        try:
            return f"Mask({self.marshal()})"
        except RecursionError:
            return "Mask(not-marshalable <too deep>)"
        except Exception as e:
            return f"Mask(not-marshalable {e})"

    def __eq__(self, value: object) -> bool:
        """Return True when another mask is structurally equal.

        :param value: Object to compare.
        :returns: ``True`` if equal, otherwise ``False``.
        """
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
        """Return a tuple of (segment count, marshaled string).

        :returns: ``(count, serialized)`` where ``count`` is the number of
            top-level segments.
        """
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
        """Serialize the mask to a string.

        :returns: Marshaled mask string.
        """
        return self._marshal()[1]

    def intersect_reset_mask(self, other: "Mask|None") -> "Mask|None":
        """Return the reset-mask intersection with another mask.

        :param other: Mask to intersect with.
        :returns: Intersected :class:`Mask` or ``None`` when ``other`` is invalid.
        """
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
        """Alias for :meth:`intersect_reset_mask`.

        :param other: Mask to intersect with.
        :returns: Intersected :class:`Mask` or ``None``.
        """
        return self.intersect_reset_mask(other)

    def intersect_dumb(self, other: "Mask|None") -> "Mask|None":
        """Return a simple intersection (no wildcard promotion).

        :param other: Mask to intersect with.
        :returns: Intersected :class:`Mask` or ``None`` when ``other`` is invalid.
        """
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
        """In-place simple intersection with another mask.

        :param other: Mask to intersect with.
        :returns: This mask instance.
        :raises ValueError: If ``other`` is not a :class:`Mask`.
        """
        if not isinstance(other, Mask):  # type: ignore[unused-ignore]
            raise ValueError(f"argument 2 must be Mask, {type(other)} given")
        ret = self.intersect_dumb(other)
        if not isinstance(ret, Mask):  # type: ignore[unused-ignore]
            raise Error(f"return should have been Mask, got {type(ret)}")
        return ret

    def __mul__(self, other: "Mask") -> "Mask":
        """Return a copy intersected with another mask.

        :param other: Mask to intersect with.
        :returns: New intersected :class:`Mask`.
        """
        cp = self.copy()
        cp *= other
        return cp

    def subtract_dumb(self, other: "Mask|None") -> None:
        """Remove paths from the mask without wildcard promotion.

        :param other: Mask to subtract.
        """
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
        """In-place simple subtraction from another mask.

        :param other: Mask to subtract.
        :returns: This mask instance.
        :raises ValueError: If ``other`` is not a :class:`Mask`.
        """
        if not isinstance(other, Mask):  # type: ignore[unused-ignore]
            raise ValueError(f"argument 2 must be Mask, {type(other)} given")
        self.subtract_dumb(other)
        return self

    def __truediv__(self, other: "Mask") -> "Mask":
        """Return a copy with simple subtraction applied.

        :param other: Mask to subtract.
        :returns: New :class:`Mask` with subtraction applied.
        """
        cp = self.copy()
        cp /= other
        return cp

    def subtract_reset_mask(self, other: "Mask|None") -> None:
        """Remove paths using reset-mask semantics.

        :param other: Mask to subtract.
        """
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
        """Parse a marshaled mask string into a :class:`Mask`.

        :param source: Mask string.
        :returns: Parsed mask tree.
        :raises Error: When parsing fails.
        """
        from .fieldmask_parser import parse

        return parse(source)

    def __isub__(self, other: "Mask|None") -> "Mask":
        """In-place reset-mask subtraction.

        :param other: Mask to subtract.
        :returns: This mask instance.
        """
        self.subtract_reset_mask(other)
        return self

    def __sub__(self, other: "Mask|None") -> "Mask":
        """Return a copy with reset-mask subtraction applied.

        :param other: Mask to subtract.
        :returns: New :class:`Mask` with subtraction applied.
        """
        cp = self.copy()
        cp -= other
        return cp
