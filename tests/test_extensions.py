"""Differential tests for namespace-owned direct protobuf extensions."""

from __future__ import annotations

import warnings
from collections.abc import Callable

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.wrappers_pb2 import BoolValue, DoubleValue, FloatValue

from nebius.base.protos.codec import (
    BOOL,
    DOUBLE,
    FLOAT,
    INT32,
    SINT32,
    STRING,
    ValueCodec,
    enum_codec,
)
from nebius.base.protos.extensions import (
    Extension,
    ExtensionRegistry,
    ExtensionValues,
)
from nebius.base.protos.wire import BinaryReader, BinaryWriter


def _reference_types():
    file_proto = descriptor_pb2.FileDescriptorProto(
        name="extensions_test.proto",
        package="extensions.test",
        syntax="proto2",
    )
    options = file_proto.message_type.add(name="Options")
    options.extension_range.add(start=100, end=200)
    child = file_proto.message_type.add(name="Child")
    child.field.add(
        name="number",
        number=1,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
    )
    child.field.add(
        name="text",
        number=2,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    state = file_proto.enum_type.add(name="State")
    state.value.add(name="STATE_UNSPECIFIED", number=0)
    state.value.add(name="STATE_ONE", number=1)
    state.value.add(name="STATE_TWO", number=2)

    optional_int = file_proto.extension.add(
        name="optional_int",
        extendee=".extensions.test.Options",
        number=100,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
    )
    repeated_sint = file_proto.extension.add(
        name="repeated_sint",
        extendee=".extensions.test.Options",
        number=101,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_SINT32,
    )
    repeated_sint.options.packed = True
    optional_string = file_proto.extension.add(
        name="optional_string",
        extendee=".extensions.test.Options",
        number=102,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    optional_child = file_proto.extension.add(
        name="optional_child",
        extendee=".extensions.test.Options",
        number=103,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".extensions.test.Child",
    )
    repeated_child = file_proto.extension.add(
        name="repeated_child",
        extendee=".extensions.test.Options",
        number=104,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".extensions.test.Child",
    )
    optional_state = file_proto.extension.add(
        name="optional_state",
        extendee=".extensions.test.Options",
        number=105,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".extensions.test.State",
    )
    repeated_state = file_proto.extension.add(
        name="repeated_state",
        extendee=".extensions.test.Options",
        number=106,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".extensions.test.State",
    )
    repeated_state.options.packed = True

    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_proto)
    options_class = message_factory.GetMessageClass(
        pool.FindMessageTypeByName("extensions.test.Options")
    )
    child_class = message_factory.GetMessageClass(
        pool.FindMessageTypeByName("extensions.test.Child")
    )
    return (
        options_class,
        child_class,
        pool.FindExtensionByName(f"extensions.test.{optional_int.name}"),
        pool.FindExtensionByName(f"extensions.test.{repeated_sint.name}"),
        pool.FindExtensionByName(f"extensions.test.{optional_string.name}"),
        pool.FindExtensionByName(f"extensions.test.{optional_child.name}"),
        pool.FindExtensionByName(f"extensions.test.{repeated_child.name}"),
        pool.FindExtensionByName(f"extensions.test.{optional_state.name}"),
        pool.FindExtensionByName(f"extensions.test.{repeated_state.name}"),
    )


(
    REFERENCE_OPTIONS,
    REFERENCE_CHILD,
    REF_INT,
    REF_REPEATED,
    REF_STRING,
    REF_CHILD,
    REF_REPEATED_CHILD,
    REF_STATE,
    REF_REPEATED_STATE,
) = _reference_types()


class DirectChild:
    """Small direct value used to exercise message-extension ownership hooks."""

    def __init__(self, *, number: int | None = None, text: str | None = None):
        self._number = 0
        self._text = ""
        self._has_number = number is not None
        self._has_text = text is not None
        self._on_mutation: Callable[[], None] | None = None
        if number is not None:
            self._number = INT32.normalize(number)
        if text is not None:
            self._text = STRING.normalize(text)

    @property
    def number(self) -> int:
        return self._number

    @number.setter
    def number(self, value: int) -> None:
        self._number = INT32.normalize(value)
        self._has_number = True
        self._changed()

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = STRING.normalize(value)
        self._has_text = True
        self._changed()

    def _changed(self) -> None:
        if self._on_mutation is not None:
            self._on_mutation()

    def bind_mutation(self, callback: Callable[[], None]) -> None:
        self._on_mutation = callback

    def copy(self) -> DirectChild:
        copied = DirectChild()
        copied._number = self._number
        copied._text = self._text
        copied._has_number = self._has_number
        copied._has_text = self._has_text
        return copied

    def merge_from(self, other: DirectChild) -> DirectChild:
        if other._has_number:
            self.number = other.number
        if other._has_text:
            self.text = other.text
        return self

    def to_bytes(self) -> bytes:
        writer = BinaryWriter()
        if self._has_number:
            writer.write_tag(1, INT32.wire_type)
            writer.write_int32(self.number)
        if self._has_text:
            writer.write_tag(2, STRING.wire_type)
            writer.write_string(self.text)
        return writer.to_bytes()

    @classmethod
    def from_bytes(cls, payload: bytes) -> DirectChild:
        value = cls()
        reader = BinaryReader(payload)
        while not reader.eof():
            field_number, wire_type, start = reader.read_tag()
            if field_number == 1 and wire_type == INT32.wire_type:
                value._number = reader.read_int32()
                value._has_number = True
            elif field_number == 2 and wire_type == STRING.wire_type:
                value._text = reader.read_string()
                value._has_text = True
            else:
                reader.skip_field(field_number, wire_type, start)
        return value

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, DirectChild)
            and self._number == other._number
            and self._text == other._text
            and self._has_number == other._has_number
            and self._has_text == other._has_text
        )


def _direct_types():
    registry = ExtensionRegistry()
    registry.add_extendee("extensions.test.Options", ((100, 200),))
    optional_int = Extension[int](
        registry,
        "extensions.test.optional_int",
        "extensions.test.Options",
        100,
        INT32,
        int,
    )
    repeated_sint = Extension[list[int]](
        registry,
        "extensions.test.repeated_sint",
        "extensions.test.Options",
        101,
        SINT32,
        list,
        repeated=True,
        packed=True,
    )
    optional_string = Extension[str](
        registry,
        "extensions.test.optional_string",
        "extensions.test.Options",
        102,
        STRING,
        str,
    )

    def normalize_child(value):
        if not isinstance(value, DirectChild):
            raise TypeError("child extension requires Child")
        return value

    def clone_child(value):
        return value.copy()

    def merge_child(destination, source):
        return destination.merge_from(source)

    child_codec = ValueCodec(
        2,
        lambda reader: DirectChild.from_bytes(reader.read_bytes()),
        lambda writer, value: writer.write_bytes(value.to_bytes()),
        normalize_child,
        DirectChild,
        packable=False,
        clone=clone_child,
        merge=merge_child,
        bind_mutation=lambda value, callback: value.bind_mutation(callback),
    )
    optional_child = Extension(
        registry,
        "extensions.test.optional_child",
        "extensions.test.Options",
        103,
        child_codec,
        DirectChild,
    )
    repeated_child = Extension(
        registry,
        "extensions.test.repeated_child",
        "extensions.test.Options",
        104,
        child_codec,
        list,
        repeated=True,
    )
    state_codec = enum_codec((0, 1, 2), closed=True)
    optional_state = Extension[int](
        registry,
        "extensions.test.optional_state",
        "extensions.test.Options",
        105,
        state_codec,
        int,
    )
    repeated_state = Extension[list[int]](
        registry,
        "extensions.test.repeated_state",
        "extensions.test.Options",
        106,
        state_codec,
        list,
        repeated=True,
        packed=True,
    )
    for extension in (
        optional_int,
        repeated_sint,
        optional_string,
        optional_child,
        repeated_child,
        optional_state,
        repeated_state,
    ):
        registry.register(extension)
    registry.freeze()
    return (
        registry,
        optional_int,
        repeated_sint,
        optional_string,
        optional_child,
        repeated_child,
        optional_state,
        repeated_state,
    )


(
    REGISTRY,
    OPTIONAL_INT,
    REPEATED_SINT,
    OPTIONAL_STRING,
    OPTIONAL_CHILD,
    REPEATED_CHILD,
    OPTIONAL_STATE,
    REPEATED_STATE,
) = _direct_types()


def _decode(payload: bytes) -> tuple[ExtensionValues, list[bytes]]:
    values = ExtensionValues(REGISTRY, "extensions.test.Options")
    unknown: list[bytes] = []
    reader = BinaryReader(payload)
    while not reader.eof():
        field_number, wire_type, start = reader.read_tag()
        extension = REGISTRY.by_number("extensions.test.Options", field_number)
        if extension is None:
            unknown.append(reader.skip_field(field_number, wire_type, start))
            continue
        result = values.try_decode(extension, reader, wire_type, start)
        if not result.consumed:
            unknown.append(reader.skip_field(field_number, wire_type, start))
        else:
            unknown.extend(result.unknown_fields)
    return values, unknown


def test_registered_extensions_match_reference_wire() -> None:
    reference = REFERENCE_OPTIONS()
    reference.Extensions[REF_INT] = -12
    reference.Extensions[REF_REPEATED].extend([-1, 0, 12345])
    reference.Extensions[REF_STRING] = "value"
    payload = reference.SerializeToString(deterministic=True)

    values, unknown = _decode(payload)
    assert unknown == []
    assert values.get(OPTIONAL_INT) == -12
    assert values.get(REPEATED_SINT) == [-1, 0, 12345]
    assert values.get(OPTIONAL_STRING) == "value"

    writer = BinaryWriter()
    values.write_to(writer)
    encoded = writer.to_bytes()
    round_tripped = REFERENCE_OPTIONS.FromString(encoded)
    assert round_tripped.Extensions[REF_INT] == -12
    assert list(round_tripped.Extensions[REF_REPEATED]) == [-1, 0, 12345]
    assert round_tripped.Extensions[REF_STRING] == "value"

    repeated_writer = BinaryWriter()
    values.write_to(repeated_writer)
    assert repeated_writer.to_bytes() == encoded


def test_repeated_packable_extension_accepts_unpacked_wire() -> None:
    writer = BinaryWriter()
    for value in (-1, 5):
        writer.write_tag(REPEATED_SINT.number, SINT32.wire_type)
        writer.write_sint32(value)
    values, unknown = _decode(writer.to_bytes())
    assert unknown == []
    assert values.get(REPEATED_SINT) == [-1, 5]


def test_wrong_wire_and_unregistered_fields_remain_raw_unknowns() -> None:
    writer = BinaryWriter()
    writer.write_tag(OPTIONAL_INT.number, STRING.wire_type)
    writer.write_string("wrong wire")
    writer.write_tag(150, INT32.wire_type)
    writer.write_int32(42)
    payload = writer.to_bytes()

    values, unknown = _decode(payload)
    assert not values.has(OPTIONAL_INT)
    assert b"".join(unknown) == payload


def test_message_extensions_merge_and_own_values() -> None:
    first = DirectChild(number=7)
    second = DirectChild(text="merged")
    repeated = DirectChild(number=11, text="repeated")
    writer = BinaryWriter()
    for child in (first, second):
        writer.write_tag(OPTIONAL_CHILD.number, OPTIONAL_CHILD.value_codec.wire_type)
        OPTIONAL_CHILD.value_codec.write(writer, child)
    writer.write_tag(REPEATED_CHILD.number, REPEATED_CHILD.value_codec.wire_type)
    REPEATED_CHILD.value_codec.write(writer, repeated)

    values, unknown = _decode(writer.to_bytes())
    assert unknown == []
    merged = values.get(OPTIONAL_CHILD)
    assert merged.number == 7
    assert merged.text == "merged"
    assert values.get(REPEATED_CHILD) == [repeated]

    copied = ExtensionValues(REGISTRY, "extensions.test.Options")
    copied.copy_from(values)
    merged.number = 99
    values.get(REPEATED_CHILD)[0].text = "changed"
    assert copied.get(OPTIONAL_CHILD).number == 7
    assert copied.get(REPEATED_CHILD)[0].text == "repeated"

    encoded = BinaryWriter()
    copied.write_to(encoded)
    reference = REFERENCE_OPTIONS.FromString(encoded.to_bytes())
    assert reference.Extensions[REF_CHILD].number == 7
    assert reference.Extensions[REF_CHILD].text == "merged"
    assert len(reference.Extensions[REF_REPEATED_CHILD]) == 1
    assert reference.Extensions[REF_REPEATED_CHILD][0].number == 11
    assert reference.Extensions[REF_REPEATED_CHILD][0].text == "repeated"


def test_message_extension_lazy_presence_and_repeated_validation() -> None:
    mutations: list[None] = []
    values = ExtensionValues(
        REGISTRY, "extensions.test.Options", lambda: mutations.append(None)
    )
    child = values.get(OPTIONAL_CHILD)
    assert child is values.get(OPTIONAL_CHILD)
    assert not values.has(OPTIONAL_CHILD)
    child.number = 4
    assert values.has(OPTIONAL_CHILD)
    assert values.get(OPTIONAL_CHILD).number == 4
    values.clear(OPTIONAL_CHILD)
    mutation_count = len(mutations)
    child.number = 5
    assert len(mutations) == mutation_count
    assert not values.has(OPTIONAL_CHILD)
    assert values.get(OPTIONAL_CHILD) is not child

    source = DirectChild(number=1)
    children = values.get(REPEATED_CHILD)
    assert children is values.get(REPEATED_CHILD)
    children.append(source)
    source.number = 9
    assert children[0].number == 1
    removed = children.pop()
    mutation_count = len(mutations)
    removed.number = 2
    assert len(mutations) == mutation_count
    assert children is values.get(REPEATED_CHILD)

    children.append(DirectChild(number=3))
    owned = children[0]
    try:
        children[0] = "bad"  # type: ignore[assignment]
    except TypeError:
        pass
    else:
        raise AssertionError("invalid message replacement was accepted")
    mutation_count = len(mutations)
    owned.number = 4
    assert len(mutations) == mutation_count + 1

    children.extend([DirectChild(number=5), DirectChild(number=6)])
    retained = children[0]
    try:
        children[::2] = [DirectChild(number=7)]
    except ValueError:
        pass
    else:
        raise AssertionError("invalid extended slice replacement was accepted")
    mutation_count = len(mutations)
    retained.number = 8
    assert len(mutations) == mutation_count + 1

    scalars = values.get(REPEATED_SINT)
    try:
        scalars.append("bad")
    except (TypeError, ValueError) as error:
        assert "int" in str(error) or "range" in str(error)
    else:
        raise AssertionError("invalid repeated scalar value was accepted")


def test_closed_enum_invalid_values_follow_reference_unknown_rules() -> None:
    writer = BinaryWriter()
    writer.write_tag(OPTIONAL_STATE.number, OPTIONAL_STATE.value_codec.wire_type)
    writer.write_int32(9)
    writer.write_tag(REPEATED_STATE.number, 2)
    writer.write_packed([1, 9, 2, -1], REPEATED_STATE.value_codec.write)
    payload = writer.to_bytes()

    values, unknown = _decode(payload)
    assert not values.has(OPTIONAL_STATE)
    assert values.get(REPEATED_STATE) == [1, 2]
    assert len(unknown) == 3

    encoded = BinaryWriter()
    values.write_to(encoded)
    for raw in unknown:
        encoded.write_raw(raw)
    reference = REFERENCE_OPTIONS.FromString(encoded.to_bytes())
    # protobuf 5.29 incorrectly reports an invalid closed singular enum as
    # present with its default value, while protobuf 6 matches proto2 semantics.
    # The direct assertions above are stable across both supported providers.
    assert reference.Extensions[REF_STATE] == 0
    assert list(reference.Extensions[REF_REPEATED_STATE]) == [1, 2]

    try:
        values.set(OPTIONAL_STATE, 9)
    except ValueError as error:
        assert "closed enum" in str(error)
    else:
        raise AssertionError("invalid closed enum value was accepted")


def test_scalar_extension_setter_coercion_matches_reference() -> None:
    values = ExtensionValues(REGISTRY, "extensions.test.Options")
    reference = REFERENCE_OPTIONS()

    values.set(OPTIONAL_INT, True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        try:
            reference.Extensions[REF_INT] = True
        except TypeError:
            # protobuf 7 stopped the bool-to-int coercion accepted by earlier
            # supported providers; retain the SDK's established behavior.
            pass
    assert values.get(OPTIONAL_INT) == 1

    values.set(OPTIONAL_STRING, b"UTF-8 value")  # type: ignore[arg-type]
    reference.Extensions[REF_STRING] = b"UTF-8 value"
    assert values.get(OPTIONAL_STRING) == reference.Extensions[REF_STRING]

    for invalid in (1.0, "1", b"1"):
        try:
            values.set(OPTIONAL_INT, invalid)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid int32 value {invalid!r} was accepted")

    reference_bool = BoolValue(value=2)
    reference_double = DoubleValue(value=True)
    reference_float = FloatValue(value=1.1)
    assert BOOL.normalize(2) is reference_bool.value is True
    assert DOUBLE.normalize(True) == reference_double.value == 1.0
    assert FLOAT.normalize(1.1) == reference_float.value
    assert FLOAT.normalize(1e100) == FloatValue(value=1e100).value
    for too_large in (1 << 100, -(1 << 100)):
        try:
            BOOL.normalize(too_large)
        except OverflowError:
            pass
        else:
            raise AssertionError("out-of-range bool integer was accepted")


def test_presence_defaults_clear_copy_merge_and_registry_identity() -> None:
    values = ExtensionValues(REGISTRY, "extensions.test.Options")
    assert values.get(OPTIONAL_INT) == 0
    assert not values.has(OPTIONAL_INT)
    values.set(OPTIONAL_INT, 0)
    assert values.has(OPTIONAL_INT)
    values.clear(OPTIONAL_INT)
    assert not values.has(OPTIONAL_INT)

    values.set(REPEATED_SINT, [1, 2])
    copied = ExtensionValues(REGISTRY, "extensions.test.Options")
    copied.copy_from(values)
    values.get(REPEATED_SINT).append(3)
    assert copied.get(REPEATED_SINT) == [1, 2]
    copied.merge_from(values)
    assert copied.get(REPEATED_SINT) == [1, 2, 1, 2, 3]
    copied.copy_from(copied)
    assert copied.get(REPEATED_SINT) == [1, 2, 1, 2, 3]
    copied.merge_from(copied)
    assert copied.get(REPEATED_SINT) == [1, 2, 1, 2, 3] * 2

    foreign = ExtensionRegistry()
    foreign.add_extendee("extensions.test.Options", ((100, 200),))
    foreign_int = Extension[int](
        foreign,
        OPTIONAL_INT.full_name,
        OPTIONAL_INT.extendee,
        OPTIONAL_INT.number,
        INT32,
        int,
    )
    foreign.register(foreign_int)
    foreign.freeze()
    try:
        values.get(foreign_int)
    except ValueError as error:
        assert "another registry" in str(error)
    else:
        raise AssertionError("foreign extension descriptor was accepted")

    unregistered = Extension[int](
        REGISTRY,
        "extensions.test.unregistered",
        OPTIONAL_INT.extendee,
        107,
        INT32,
        int,
    )
    try:
        values.get(unregistered)
    except ValueError as error:
        assert "not registered" in str(error)
    else:
        raise AssertionError("unregistered extension descriptor was accepted")


def test_registry_rejects_invalid_state_and_conflicts() -> None:
    unfrozen = ExtensionRegistry()
    unfrozen.add_extendee("extensions.test.Options", ((100, 200),))
    try:
        ExtensionValues(unfrozen, "extensions.test.Options")
    except RuntimeError as error:
        assert "frozen" in str(error)
    else:
        raise AssertionError("unfrozen extension registry was accepted")

    extension = Extension[int](
        unfrozen,
        "extensions.test.value",
        "extensions.test.Options",
        100,
        INT32,
        int,
    )
    unfrozen.register(extension)
    for conflicting in (
        Extension[int](
            unfrozen,
            "extensions.test.other_name",
            "extensions.test.Options",
            100,
            INT32,
            int,
        ),
        Extension[int](
            unfrozen,
            "extensions.test.value",
            "extensions.test.Options",
            101,
            INT32,
            int,
        ),
    ):
        try:
            unfrozen.register(conflicting)
        except ValueError as error:
            assert "conflicting" in str(error)
        else:
            raise AssertionError("conflicting extension was accepted")

    outside = Extension[int](
        unfrozen,
        "extensions.test.outside",
        "extensions.test.Options",
        99,
        INT32,
        int,
    )
    try:
        unfrozen.register(outside)
    except ValueError as error:
        assert "outside" in str(error)
    else:
        raise AssertionError("out-of-range extension was accepted")

    unfrozen.freeze()
    try:
        unfrozen.register(extension)
    except RuntimeError as error:
        assert "frozen" in str(error)
    else:
        raise AssertionError("frozen extension registry was mutated")
