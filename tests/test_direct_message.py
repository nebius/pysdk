"""Differential tests for provider-free direct message state."""

from __future__ import annotations

from google.protobuf import (
    descriptor_pb2,
    descriptor_pool,
    message_factory,
)
from google.protobuf.message import DecodeError, EncodeError

from nebius.api.google.protobuf import (
    Any as ProtoAny,
)
from nebius.api.google.protobuf import (
    Duration,
    ListValue,
    NullValue,
    Struct,
    Timestamp,
    Value,
)
from nebius.base.fieldmask import FieldKey, Mask
from nebius.base.protos.codec import (
    BOOL,
    BYTES,
    DOUBLE,
    INT32,
    INT64,
    SINT32,
    STRING,
    enum_codec,
)
from nebius.base.protos.direct import Field, Message, message_codec
from nebius.base.protos.extensions import Extension, ExtensionRegistry
from nebius.base.protos.wire import BinaryWriter


def _reference_types():
    file_proto = descriptor_pb2.FileDescriptorProto(
        name="direct_test.proto",
        package="direct.test",
        syntax="proto3",
    )
    state = file_proto.enum_type.add(name="State")
    state.value.add(name="STATE_UNSPECIFIED", number=0)
    state.value.add(name="STATE_READY", number=1)
    child = file_proto.message_type.add(name="Child")
    child.field.add(
        name="value",
        number=1,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
    )
    child.field.add(
        name="note",
        number=2,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )

    sample = file_proto.message_type.add(name="Sample")
    sample.oneof_decl.add(name="choice")
    sample.oneof_decl.add(name="_optional_count")

    def add_field(name, number, field_type, **kwargs):
        return sample.field.add(
            name=name,
            number=number,
            label=kwargs.pop(
                "label", descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
            ),
            type=field_type,
            **kwargs,
        )

    add_field("count", 1, descriptor_pb2.FieldDescriptorProto.TYPE_INT32)
    title = add_field("title", 2, descriptor_pb2.FieldDescriptorProto.TYPE_STRING)
    title.json_name = "displayTitle"
    child_field = add_field(
        "child",
        3,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".direct.test.Child",
    )
    child_field.json_name = "directChild"
    nums = add_field(
        "nums",
        4,
        descriptor_pb2.FieldDescriptorProto.TYPE_SINT32,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
    )
    nums.options.packed = True
    add_field(
        "children",
        5,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type_name=".direct.test.Child",
    )
    add_field(
        "text",
        6,
        descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
        oneof_index=0,
    )
    add_field(
        "selected_child",
        7,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".direct.test.Child",
        oneof_index=0,
    )
    optional = add_field(
        "optional_count",
        8,
        descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
        oneof_index=1,
    )
    optional.proto3_optional = True

    labels_entry = sample.nested_type.add(name="LabelsEntry")
    labels_entry.options.map_entry = True
    labels_entry.field.add(
        name="key",
        number=1,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    labels_entry.field.add(
        name="value",
        number=2,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_INT32,
    )
    add_field(
        "labels",
        9,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type_name=".direct.test.Sample.LabelsEntry",
    )

    child_map_entry = sample.nested_type.add(name="ChildMapEntry")
    child_map_entry.options.map_entry = True
    child_map_entry.field.add(
        name="key",
        number=1,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    child_map_entry.field.add(
        name="value",
        number=2,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".direct.test.Child",
    )
    add_field(
        "child_map",
        10,
        descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type_name=".direct.test.Sample.ChildMapEntry",
    )
    add_field(
        "state",
        11,
        descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".direct.test.State",
    )
    add_field("big", 12, descriptor_pb2.FieldDescriptorProto.TYPE_INT64)
    add_field("payload", 13, descriptor_pb2.FieldDescriptorProto.TYPE_BYTES)
    add_field("ratio", 14, descriptor_pb2.FieldDescriptorProto.TYPE_DOUBLE)
    add_field("active", 15, descriptor_pb2.FieldDescriptorProto.TYPE_BOOL)

    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_proto)
    return (
        message_factory.GetMessageClass(
            pool.FindMessageTypeByName("direct.test.Child")
        ),
        message_factory.GetMessageClass(
            pool.FindMessageTypeByName("direct.test.Sample")
        ),
    )


REFERENCE_CHILD, REFERENCE_SAMPLE = _reference_types()


def _reference_proto2_type():
    file_proto = descriptor_pb2.FileDescriptorProto(
        name="direct_proto2_test.proto",
        package="direct.test",
        syntax="proto2",
    )
    state = file_proto.enum_type.add(name="LegacyState")
    state.value.add(name="LEGACY_ZERO", number=0)
    state.value.add(name="LEGACY_ONE", number=1)
    legacy = file_proto.message_type.add(name="Legacy")
    legacy.field.add(
        name="name",
        number=1,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REQUIRED,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_STRING,
    )
    states = legacy.field.add(
        name="states",
        number=2,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_ENUM,
        type_name=".direct.test.LegacyState",
    )
    states.options.packed = True
    host = file_proto.message_type.add(name="ExtensionHost")
    host.extension_range.add(start=100, end=200)
    required_extension = file_proto.extension.add(
        name="required_extension",
        extendee=".direct.test.ExtensionHost",
        number=100,
        label=descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL,
        type=descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE,
        type_name=".direct.test.Legacy",
    )
    pool = descriptor_pool.DescriptorPool()
    pool.Add(file_proto)
    return (
        message_factory.GetMessageClass(
            pool.FindMessageTypeByName("direct.test.Legacy")
        ),
        message_factory.GetMessageClass(
            pool.FindMessageTypeByName("direct.test.ExtensionHost")
        ),
        pool.FindExtensionByName(f"direct.test.{required_extension.name}"),
    )


REFERENCE_LEGACY, REFERENCE_EXTENSION_HOST, REF_REQUIRED_EXTENSION = (
    _reference_proto2_type()
)


class Child(Message):
    __PROTO_FULL_NAME__ = "direct.test.Child"

    @property
    def value(self) -> int:
        return self._get_field(CHILD_VALUE)

    @value.setter
    def value(self, value: int) -> None:
        self._set_field(CHILD_VALUE, value)

    @property
    def note(self) -> str:
        return self._get_field(CHILD_NOTE)

    @note.setter
    def note(self, value: str) -> None:
        self._set_field(CHILD_NOTE, value)


CHILD_VALUE = Field("value", "value", 1, INT32)
CHILD_NOTE = Field("note", "note", 2, STRING)
Child.__FIELDS__ = (CHILD_VALUE, CHILD_NOTE)
CHILD_CODEC = message_codec(lambda: Child)


class Sample(Message):
    __PROTO_FULL_NAME__ = "direct.test.Sample"

    @property
    def count(self) -> int:
        return self._get_field(SAMPLE_COUNT)

    @count.setter
    def count(self, value: int) -> None:
        self._set_field(SAMPLE_COUNT, value)

    @property
    def title(self) -> str:
        return self._get_field(SAMPLE_TITLE)

    @title.setter
    def title(self, value: str) -> None:
        self._set_field(SAMPLE_TITLE, value)

    @property
    def child(self) -> Child:
        return self._get_field(SAMPLE_CHILD)

    @child.setter
    def child(self, value: Child) -> None:
        self._set_field(SAMPLE_CHILD, value)

    @property
    def nums(self):
        return self._get_field(SAMPLE_NUMS)

    @nums.setter
    def nums(self, value) -> None:
        self._set_field(SAMPLE_NUMS, value)

    @property
    def children(self):
        return self._get_field(SAMPLE_CHILDREN)

    @children.setter
    def children(self, value) -> None:
        self._set_field(SAMPLE_CHILDREN, value)

    @property
    def text(self) -> str | None:
        return self._get_field(SAMPLE_TEXT, absent_is_none=True)

    @text.setter
    def text(self, value: str | None) -> None:
        self._set_field(SAMPLE_TEXT, value)

    @property
    def selected_child(self) -> Child | None:
        return self._get_field(SAMPLE_SELECTED_CHILD, absent_is_none=True)

    @selected_child.setter
    def selected_child(self, value: Child | None) -> None:
        self._set_field(SAMPLE_SELECTED_CHILD, value)

    def selected_child_view(self) -> Child:
        return self._get_field(SAMPLE_SELECTED_CHILD)

    @property
    def optional_count(self) -> int | None:
        return self._get_field(SAMPLE_OPTIONAL_COUNT, absent_is_none=True)

    @optional_count.setter
    def optional_count(self, value: int | None) -> None:
        self._set_field(SAMPLE_OPTIONAL_COUNT, value)

    @property
    def labels(self):
        return self._get_field(SAMPLE_LABELS)

    @labels.setter
    def labels(self, value) -> None:
        self._set_field(SAMPLE_LABELS, value)

    @property
    def child_map(self):
        return self._get_field(SAMPLE_CHILD_MAP)

    @child_map.setter
    def child_map(self, value) -> None:
        self._set_field(SAMPLE_CHILD_MAP, value)

    @property
    def state(self) -> int:
        return self._get_field(SAMPLE_STATE)

    @state.setter
    def state(self, value: int) -> None:
        self._set_field(SAMPLE_STATE, value)

    @property
    def big(self) -> int:
        return self._get_field(SAMPLE_BIG)

    @big.setter
    def big(self, value: int) -> None:
        self._set_field(SAMPLE_BIG, value)

    @property
    def payload(self) -> bytes:
        return self._get_field(SAMPLE_PAYLOAD)

    @payload.setter
    def payload(self, value: bytes) -> None:
        self._set_field(SAMPLE_PAYLOAD, value)

    @property
    def ratio(self) -> float:
        return self._get_field(SAMPLE_RATIO)

    @ratio.setter
    def ratio(self, value: float) -> None:
        self._set_field(SAMPLE_RATIO, value)

    @property
    def active(self) -> bool:
        return self._get_field(SAMPLE_ACTIVE)

    @active.setter
    def active(self, value: bool) -> None:
        self._set_field(SAMPLE_ACTIVE, value)


SAMPLE_COUNT = Field("count", "count", 1, INT32)
SAMPLE_TITLE = Field("title", "title", 2, STRING, json_name="displayTitle")
SAMPLE_CHILD = Field("child", "child", 3, CHILD_CODEC, json_name="directChild")
SAMPLE_NUMS = Field("nums", "nums", 4, SINT32, repeated=True, packed=True)
SAMPLE_CHILDREN = Field("children", "children", 5, CHILD_CODEC, repeated=True)
SAMPLE_TEXT = Field("text", "text", 6, STRING, oneof="choice")
SAMPLE_SELECTED_CHILD = Field(
    "selected_child", "selected_child", 7, CHILD_CODEC, oneof="choice"
)
SAMPLE_OPTIONAL_COUNT = Field(
    "optional_count",
    "optional_count",
    8,
    INT32,
    explicit_presence=True,
    oneof="_optional_count",
)
SAMPLE_LABELS = Field("labels", "labels", 9, INT32, map_key_codec=STRING)
SAMPLE_CHILD_MAP = Field(
    "child_map", "child_map", 10, CHILD_CODEC, map_key_codec=STRING
)
SAMPLE_STATE = Field(
    "state",
    "state",
    11,
    enum_codec((0, 1), names={"STATE_UNSPECIFIED": 0, "STATE_READY": 1}),
)
SAMPLE_BIG = Field("big", "big", 12, INT64)
SAMPLE_PAYLOAD = Field("payload", "payload", 13, BYTES)
SAMPLE_RATIO = Field("ratio", "ratio", 14, DOUBLE)
SAMPLE_ACTIVE = Field("active", "active", 15, BOOL)
Sample.__FIELDS__ = (
    SAMPLE_COUNT,
    SAMPLE_TITLE,
    SAMPLE_CHILD,
    SAMPLE_NUMS,
    SAMPLE_CHILDREN,
    SAMPLE_TEXT,
    SAMPLE_SELECTED_CHILD,
    SAMPLE_OPTIONAL_COUNT,
    SAMPLE_LABELS,
    SAMPLE_CHILD_MAP,
    SAMPLE_STATE,
    SAMPLE_BIG,
    SAMPLE_PAYLOAD,
    SAMPLE_RATIO,
    SAMPLE_ACTIVE,
)
SAMPLE_CODEC = message_codec(lambda: Sample)


class Envelope(Message):
    __PROTO_FULL_NAME__ = "direct.test.Envelope"

    @property
    def sample(self) -> Sample:
        return self._get_field(ENVELOPE_SAMPLE)

    @sample.setter
    def sample(self, value: Sample) -> None:
        self._set_field(ENVELOPE_SAMPLE, value)


ENVELOPE_SAMPLE = Field("sample", "sample", 1, SAMPLE_CODEC)
Envelope.__FIELDS__ = (ENVELOPE_SAMPLE,)


class Legacy(Message):
    __PROTO_FULL_NAME__ = "direct.test.Legacy"

    @property
    def name(self) -> str:
        return self._get_field(LEGACY_NAME)

    @name.setter
    def name(self, value: str) -> None:
        self._set_field(LEGACY_NAME, value)

    @property
    def states(self):
        return self._get_field(LEGACY_STATES)


LEGACY_NAME = Field("name", "name", 1, STRING, explicit_presence=True, required=True)
LEGACY_STATES = Field(
    "states",
    "states",
    2,
    enum_codec(
        (0, 1),
        closed=True,
        names={"LEGACY_ZERO": 0, "LEGACY_ONE": 1},
    ),
    repeated=True,
    packed=True,
)
Legacy.__FIELDS__ = (LEGACY_NAME, LEGACY_STATES)
LEGACY_CODEC = message_codec(lambda: Legacy)

EXTENSION_REGISTRY = ExtensionRegistry()
EXTENSION_REGISTRY.add_extendee("direct.test.ExtensionHost", ((100, 200),))
REQUIRED_EXTENSION = Extension[Legacy](
    EXTENSION_REGISTRY,
    "direct.test.required_extension",
    "direct.test.ExtensionHost",
    100,
    LEGACY_CODEC,
    Legacy,
)
EXTENSION_REGISTRY.register(REQUIRED_EXTENSION)
EXTENSION_REGISTRY.freeze()


class ExtensionHost(Message):
    __PROTO_FULL_NAME__ = "direct.test.ExtensionHost"
    __EXTENSION_REGISTRY__ = EXTENSION_REGISTRY


class RequiredMapHost(Message):
    __PROTO_FULL_NAME__ = "direct.test.RequiredMapHost"

    @property
    def names(self):
        return self._get_field(REQUIRED_NAMES)

    @property
    def bools(self):
        return self._get_field(REQUIRED_BOOLS)

    @property
    def ints(self):
        return self._get_field(REQUIRED_INTS)


REQUIRED_NAMES = Field("names", "names", 1, LEGACY_CODEC, map_key_codec=STRING)
REQUIRED_BOOLS = Field("bools", "bools", 2, LEGACY_CODEC, map_key_codec=BOOL)
REQUIRED_INTS = Field("ints", "ints", 3, LEGACY_CODEC, map_key_codec=INT32)
RequiredMapHost.__FIELDS__ = (REQUIRED_NAMES, REQUIRED_BOOLS, REQUIRED_INTS)


class ClosedEnumMap(Message):
    __PROTO_FULL_NAME__ = "direct.test.ClosedEnumMap"

    @property
    def values(self):
        return self._get_field(CLOSED_ENUM_VALUES)


CLOSED_ENUM_VALUES = Field(
    "values",
    "values",
    1,
    enum_codec((0, 1), closed=True),
    map_key_codec=STRING,
)
ClosedEnumMap.__FIELDS__ = (CLOSED_ENUM_VALUES,)


def test_binary_round_trip_matches_reference_in_both_directions() -> None:
    reference = REFERENCE_SAMPLE(
        count=12,
        title="sample",
        child=REFERENCE_CHILD(value=7, note="nested"),
        nums=[-1, 0, 9],
        children=[REFERENCE_CHILD(value=1), REFERENCE_CHILD(note="two")],
        selected_child=REFERENCE_CHILD(value=11),
        optional_count=0,
    )
    payload = reference.SerializeToString(deterministic=True)
    direct = Sample.FromString(payload)
    assert direct.count == 12
    assert direct.title == "sample"
    assert direct.child.value == 7
    assert direct.nums == [-1, 0, 9]
    assert [child.note for child in direct.children] == ["", "two"]
    assert direct.WhichOneof("choice") == "selected_child"
    assert direct.optional_count == 0
    assert direct.HasField("optional_count")
    assert direct.SerializeToString(deterministic=True) == payload

    constructed = Sample(
        count=12,
        title=b"sample",
        child=Child(value=7, note="nested"),
        nums=[-1, 0, 9],
        children=[Child(value=1), Child(note="two")],
        selected_child=Child(value=11),
        optional_count=0,
    )
    parsed = REFERENCE_SAMPLE.FromString(
        constructed.SerializeToString(deterministic=True)
    )
    assert parsed == reference


def test_lazy_message_presence_oneof_and_reset_mask() -> None:
    sample = Sample()
    assert not sample.HasField("_optional_count")
    assert sample.WhichOneof("_optional_count") is None
    child = sample.child
    assert str(sample.get_mask()) == "Mask(child)"
    assert not sample.HasField("child")
    child.value = 1
    assert sample.HasField("child")

    selected = sample.selected_child_view()
    assert sample.WhichOneof("choice") is None
    selected.note = "selected"
    assert sample.WhichOneof("choice") == "selected_child"
    sample.text = "replacement"
    assert sample.WhichOneof("choice") == "text"
    assert sample.selected_child is None
    selected.value = 99
    assert sample.WhichOneof("choice") == "text"

    sample.optional_count = 0
    assert sample.HasField("optional_count")
    assert sample.HasField("_optional_count")
    assert sample.WhichOneof("_optional_count") == "optional_count"
    sample.optional_count = None
    assert not sample.HasField("optional_count")
    assert not sample.HasField("_optional_count")
    assert sample.WhichOneof("_optional_count") is None
    assert "optional_count" in str(sample.get_mask())


def test_constructor_hydration_and_clear_reset_masks() -> None:
    sample = Sample(count=0, nums=None)
    assert str(sample.get_mask()) == "Mask()"
    nums = sample.nums
    sample.nums = [1]
    sample.nums = None
    assert sample.nums is nums
    assert sample.nums == []
    assert "nums" in str(sample.get_mask())

    sample.Clear()
    assert str(sample.get_mask()) == "Mask()"
    sample.ClearField("title")
    assert str(sample.get_mask()) == "Mask(title)"


def test_full_update_reset_mask_covers_defaults_and_nested_messages() -> None:
    sample = Sample(count=1, child=Child(value=2), nums=[3])
    mask = sample.get_full_update_reset_mask()
    rendered = mask.marshal()
    assert FieldKey("count") not in mask.field_parts
    assert "title" in rendered
    assert "child.note" in rendered
    assert "child.value" not in rendered
    assert "nums" not in rendered
    assert _full_field_mask(sample, "children") == Mask()
    assert "optional_count" in rendered


def test_assignment_and_repeated_mutation_copy_without_aliasing() -> None:
    source = Child(value=1)
    sample = Sample(child=source, children=[source])
    source.value = 2
    assert sample.child.value == 1
    assert sample.children[0].value == 1

    children = sample.children
    inserted = Child(value=3)
    children.append(inserted)
    inserted.value = 4
    assert children[-1].value == 3
    try:
        children[0] = "bad"
    except TypeError:
        pass
    else:
        raise AssertionError("invalid repeated message value was accepted")
    children[0].value = 5
    assert sample.children[0].value == 5
    assert children is sample.children


def test_maps_match_reference_and_own_message_values() -> None:
    reference = REFERENCE_SAMPLE(
        labels={"a": 1, "b": 2},
        child_map={"first": REFERENCE_CHILD(value=3)},
    )
    direct = Sample.FromString(reference.SerializeToString(deterministic=True))
    assert direct.labels == {"a": 1, "b": 2}
    assert direct.child_map["first"].value == 3
    round_tripped = REFERENCE_SAMPLE.FromString(
        direct.SerializeToString(deterministic=True)
    )
    assert round_tripped == reference

    source = Child(value=4)
    direct.child_map["copied"] = source
    source.value = 5
    assert direct.child_map["copied"].value == 4
    encoded = direct.SerializeToString(deterministic=True)
    assert REFERENCE_SAMPLE.FromString(encoded).child_map["copied"].value == 4


def test_map_missing_keys_duplicate_entries_and_stable_identity() -> None:
    sample = Sample()
    labels = sample.labels
    child_map = sample.child_map
    assert "absent" not in labels
    assert "absent" not in child_map
    assert len(labels) == len(child_map) == 0
    assert labels.get("missing") is None
    assert len(labels) == 0
    assert labels["missing"] == 0
    assert len(labels) == 1
    assert labels.setdefault("default", 7) == 7
    assert labels["default"] == 7
    try:
        labels.setdefault("default")
    except ValueError:
        pass
    else:
        raise AssertionError("scalar map setdefault accepted no default")
    missing_child = child_map["missing"]
    assert len(child_map) == 1
    missing_child.note = "present"
    assert sample.child_map["missing"].note == "present"
    try:
        child_map.setdefault("missing", Child())
    except NotImplementedError:
        pass
    else:
        raise AssertionError("message map setdefault was accepted")

    first = REFERENCE_CHILD(value=1).SerializeToString(deterministic=True)
    second = REFERENCE_CHILD(note="second").SerializeToString(deterministic=True)

    def entry(payload: bytes) -> bytes:
        nested = BinaryWriter()
        nested.write_tag(1, STRING.wire_type)
        nested.write_string("duplicate")
        nested.write_tag(2, CHILD_CODEC.wire_type)
        nested.write_bytes(payload)
        outer = BinaryWriter()
        outer.write_tag(SAMPLE_CHILD_MAP.number, 2)
        outer.write_bytes(nested.to_bytes())
        return outer.to_bytes()

    parsed = Sample.FromString(entry(first) + entry(second))
    assert parsed.child_map["duplicate"].value == 0
    assert parsed.child_map["duplicate"].note == "second"

    combined = BinaryWriter()
    combined.write_tag(1, STRING.wire_type)
    combined.write_string("combined")
    combined.write_tag(2, CHILD_CODEC.wire_type)
    combined.write_bytes(first)
    combined.write_tag(2, CHILD_CODEC.wire_type)
    combined.write_bytes(second)
    outer = BinaryWriter()
    outer.write_tag(SAMPLE_CHILD_MAP.number, 2)
    outer.write_bytes(combined.to_bytes())
    merged = Sample.FromString(outer.to_bytes())
    assert merged.child_map["combined"].value == 1
    assert merged.child_map["combined"].note == "second"

    copied = Sample(labels={"x": 1}, child_map={"x": Child(value=1)})
    copied.CopyFrom(sample)
    assert copied.labels is not labels
    copied_labels = copied.labels
    copied_children = copied.child_map
    copied.Clear()
    assert copied.labels is copied_labels
    assert copied.child_map is copied_children


def test_map_rejected_assignment_is_atomic_and_wrong_wire_is_unknown() -> None:
    sample = Sample(child_map={"kept": Child(value=1)})
    kept = sample.child_map["kept"]
    try:
        sample.child_map["kept"] = "bad"
    except TypeError:
        pass
    else:
        raise AssertionError("invalid message map assignment was accepted")
    kept.value = 2
    assert sample.child_map["kept"].value == 2

    writer = BinaryWriter()
    writer.write_tag(SAMPLE_LABELS.number, INT32.wire_type)
    writer.write_int32(9)
    payload = writer.to_bytes()
    parsed = Sample.FromString(payload)
    assert parsed.labels == {}
    assert parsed.SerializeToString() == payload


def test_invalid_map_entry_is_preserved_as_one_unknown_outer_field() -> None:
    def outer(entry: bytes) -> bytes:
        writer = BinaryWriter()
        writer.write_tag(SAMPLE_LABELS.number, 2)
        writer.write_bytes(entry)
        return writer.to_bytes()

    with_unknown = BinaryWriter()
    with_unknown.write_tag(1, STRING.wire_type)
    with_unknown.write_string("key")
    with_unknown.write_tag(2, INT32.wire_type)
    with_unknown.write_int32(1)
    with_unknown.write_tag(3, INT32.wire_type)
    with_unknown.write_int32(9)

    wrong_key_wire = BinaryWriter()
    wrong_key_wire.write_tag(1, INT32.wire_type)
    wrong_key_wire.write_int32(7)
    wrong_key_wire.write_tag(2, INT32.wire_type)
    wrong_key_wire.write_int32(2)

    for entry in (with_unknown.to_bytes(), wrong_key_wire.to_bytes()):
        payload = outer(entry)
        direct = Sample.FromString(payload)
        reference = REFERENCE_SAMPLE.FromString(payload)
        assert direct.labels == {}
        assert dict(reference.labels) == {}
        assert direct.SerializeToString(deterministic=True) == payload
        assert (
            dict(
                REFERENCE_SAMPLE.FromString(
                    reference.SerializeToString(deterministic=True)
                ).labels
            )
            == {}
        )

    invalid_enum_entry = BinaryWriter()
    invalid_enum_entry.write_tag(1, STRING.wire_type)
    invalid_enum_entry.write_string("invalid")
    invalid_enum_entry.write_tag(2, INT32.wire_type)
    invalid_enum_entry.write_int32(9)
    invalid_enum_outer = BinaryWriter()
    invalid_enum_outer.write_tag(CLOSED_ENUM_VALUES.number, 2)
    invalid_enum_outer.write_bytes(invalid_enum_entry.to_bytes())
    invalid_enum_payload = invalid_enum_outer.to_bytes()
    closed = ClosedEnumMap.FromString(invalid_enum_payload)
    assert closed.values == {}
    assert closed.SerializeToString() == invalid_enum_payload


def test_deterministic_map_output_is_independent_of_insertion_order() -> None:
    left = Sample(labels={"z": 1, "a": 2, "middle": 3})
    right = Sample(labels={"middle": 3, "z": 1, "a": 2})
    assert left.SerializeToString(deterministic=True) == right.SerializeToString(
        deterministic=True
    )
    assert Envelope(sample=left).SerializeToString(deterministic=True) == Envelope(
        sample=right
    ).SerializeToString(deterministic=True)


def test_copy_merge_clear_and_container_identity() -> None:
    source = Sample(
        child=Child(value=1),
        nums=[1, 2],
        children=[Child(note="one")],
        optional_count=0,
    )
    destination = Sample(nums=[9])
    nums = destination.nums
    children = destination.children
    destination.CopyFrom(source)
    assert destination.nums is nums
    assert destination.children is children
    source.child.value = 2
    source.children[0].note = "changed"
    assert destination.child.value == 1
    assert destination.children[0].note == "one"

    destination.MergeFrom(destination)
    assert destination.nums == [1, 2, 1, 2]
    assert [child.note for child in destination.children] == ["one", "one"]
    destination.Clear()
    assert destination.nums is nums
    assert destination.children is children
    assert destination.nums == []
    assert destination.SerializeToString() == b""


def test_unknown_and_wrong_wire_fields_are_preserved() -> None:
    writer = BinaryWriter()
    writer.write_tag(SAMPLE_COUNT.number, STRING.wire_type)
    writer.write_string("wrong")
    writer.write_tag(99, INT32.wire_type)
    writer.write_int32(42)
    payload = writer.to_bytes()
    direct = Sample.FromString(payload)
    assert direct.count == 0
    assert direct.SerializeToString(deterministic=True) == payload

    copied = Sample()
    copied.CopyFrom(direct)
    assert copied.SerializeToString() == payload
    copied.MergeFrom(copied)
    assert copied.SerializeToString() == payload * 2
    copied.ClearField("count")
    assert copied.SerializeToString() == payload * 2


def test_multiple_singular_message_occurrences_merge() -> None:
    first = REFERENCE_CHILD(value=7).SerializeToString(deterministic=True)
    second = REFERENCE_CHILD(note="merged").SerializeToString(deterministic=True)
    writer = BinaryWriter()
    writer.write_tag(SAMPLE_CHILD.number, CHILD_CODEC.wire_type)
    writer.write_bytes(first)
    writer.write_tag(SAMPLE_CHILD.number, CHILD_CODEC.wire_type)
    writer.write_bytes(second)
    direct = Sample.FromString(writer.to_bytes())
    assert direct.child.value == 7
    assert direct.child.note == "merged"
    reference = REFERENCE_SAMPLE.FromString(direct.SerializeToString())
    assert reference.child.value == 7
    assert reference.child.note == "merged"


def test_malformed_input_and_presence_errors_match_contract() -> None:
    for payload in (b"\x00", b"\x08\x80", b"\x1a\x02\x08"):
        try:
            Sample.FromString(payload)
        except DecodeError:
            pass
        else:
            raise AssertionError(f"malformed input {payload!r} was accepted")
    for name in ("count", "nums"):
        try:
            Sample().HasField(name)
        except ValueError:
            pass
        else:
            raise AssertionError(f"presence was reported for {name}")


def test_provider_interop_constructor_does_not_retain_backing_message() -> None:
    provider = REFERENCE_SAMPLE(count=3, child=REFERENCE_CHILD(value=4))
    direct = Sample(provider)
    provider.count = 9
    provider.child.value = 10
    assert direct.count == 3
    assert direct.child.value == 4
    assert not hasattr(direct, "__pb2_message__")
    assert direct == direct
    assert direct != Sample.FromString(direct.SerializeToString())
    assert isinstance(hash(direct), int)


def test_generated_compatibility_helpers_and_repr_redact_secrets() -> None:
    class Secrets(Message):
        __PROTO_FULL_NAME__ = "direct.test.Secrets"

    public = Field("public_value", "public_value", 1, STRING)
    sensitive = Field("secret", "secret", 2, STRING, sensitive=True)
    credentials = Field("credentials", "credentials", 3, STRING, credentials=True)
    selected = Field("selected_name", "selected_name", 4, STRING, oneof="choice")
    Secrets.__FIELDS__ = (public, sensitive, credentials, selected)
    Secrets.__PY_TO_PB2__ = {
        "public_value": "public_value",
        "secret": "secret",
        "credentials": "credentials",
        "selected_name": "selected_name",
        "choice": "choice",
    }

    message = Secrets(
        public_value="visible",
        secret="must-not-leak",
        credentials="must-not-leak-either",
        selected_name="chosen",
    )
    rendered = repr(message)
    assert "visible" in rendered
    assert "must-not-leak" not in rendered
    assert rendered.count("**HIDDEN**") == 2
    assert not message.is_default("public_value")
    assert Secrets().is_default("public_value")
    assert message.which_field_in_oneof("choice") == "selected_name"
    assert message.check_presence("selected_name")
    assert dir(message) == [
        "choice",
        "credentials",
        "public_value",
        "secret",
        "selected_name",
    ]


def test_required_fields_and_closed_declared_enums_match_reference() -> None:
    direct = Legacy()
    assert direct.FindInitializationErrors() == ["name"]
    assert not direct.IsInitialized()
    try:
        direct.SerializeToString()
    except EncodeError:
        pass
    else:
        raise AssertionError("missing proto2 required field was encoded")

    writer = BinaryWriter()
    writer.write_tag(LEGACY_NAME.number, STRING.wire_type)
    writer.write_string("set")
    writer.write_tag(LEGACY_STATES.number, 2)
    writer.write_packed([0, 9, 1, -1], LEGACY_STATES.codec.write)
    payload = writer.to_bytes()
    direct.ParseFromString(payload)
    assert direct.states == [0, 1]
    assert direct.IsInitialized()
    expected = REFERENCE_LEGACY.FromString(payload).SerializeToString(
        deterministic=True
    )
    assert direct.SerializeToString(deterministic=True) == expected


def test_required_fields_inside_message_extensions_are_reported() -> None:
    reference = REFERENCE_EXTENSION_HOST()
    reference.Extensions[REF_REQUIRED_EXTENSION].SetInParent()
    direct = ExtensionHost()
    direct.set_extension(REQUIRED_EXTENSION, Legacy())
    assert direct.FindInitializationErrors() == reference.FindInitializationErrors()
    assert direct.FindInitializationErrors() == ["required_extension.name"]
    assert not direct.IsInitialized()
    try:
        direct.SerializeToString()
    except EncodeError:
        pass
    else:
        raise AssertionError("invalid message extension was encoded")


def test_required_message_map_paths_use_provider_key_format() -> None:
    direct = RequiredMapHost()
    direct.names["x"]
    direct.bools[True]
    direct.ints[3]
    assert direct.FindInitializationErrors() == [
        'names["x"].name',
        "bools[true].name",
        "ints[3].name",
    ]
    escaped = RequiredMapHost()
    escaped.names['a"b\\c\n']
    assert escaped.FindInitializationErrors() == ['names["a\\"b\\c\n"].name']


def _full_field_mask(message: Message, proto_name: str) -> Mask | None:
    return message.get_full_update_reset_mask().field_parts.get(FieldKey(proto_name))


def test_full_reset_mask_uses_proto_names_not_python_or_json_names() -> None:
    class Renamed(Message):
        __PROTO_FULL_NAME__ = "reset.mask.Renamed"

    Renamed.__FIELDS__ = (
        Field(
            "proto_name",
            "python_name",
            1,
            STRING,
            json_name="jsonName",
        ),
    )

    assert Renamed().get_full_update_reset_mask().marshal() == "proto_name"


def test_full_reset_mask_scalar_defaults_ignore_presence() -> None:
    empty = Sample()
    assert _full_field_mask(empty, "count") == Mask()
    assert _full_field_mask(empty, "optional_count") == Mask()
    assert _full_field_mask(empty, "text") == Mask()

    defaults_with_presence = Sample(count=0, optional_count=0, text="")
    assert _full_field_mask(defaults_with_presence, "count") == Mask()
    assert _full_field_mask(defaults_with_presence, "optional_count") == Mask()
    assert _full_field_mask(defaults_with_presence, "text") == Mask()

    nondefaults = Sample(count=1, optional_count=1, text="x")
    assert _full_field_mask(nondefaults, "count") is None
    assert _full_field_mask(nondefaults, "optional_count") is None
    assert _full_field_mask(nondefaults, "text") is None


def test_full_reset_mask_optional_scalar_defaults_of_every_kind() -> None:
    class OptionalScalars(Message):
        __PROTO_FULL_NAME__ = "reset.mask.OptionalScalars"

    OptionalScalars.__FIELDS__ = (
        Field("bool_value", "bool_value", 1, BOOL, explicit_presence=True),
        Field("bytes_value", "bytes_value", 2, BYTES, explicit_presence=True),
        Field("double_value", "double_value", 3, DOUBLE, explicit_presence=True),
        Field("int_value", "int_value", 4, INT32, explicit_presence=True),
        Field("string_value", "string_value", 5, STRING, explicit_presence=True),
        Field(
            "enum_value",
            "enum_value",
            6,
            enum_codec((0, 1), names={"ZERO": 0, "ONE": 1}),
            explicit_presence=True,
        ),
        Field(
            "nonzero_default",
            "nonzero_default",
            7,
            INT32,
            explicit_presence=True,
            default_factory=lambda: 7,
        ),
    )
    names = tuple(field.proto_name for field in OptionalScalars.__FIELDS__)

    absent = OptionalScalars()
    defaults = OptionalScalars(
        bool_value=False,
        bytes_value=b"",
        double_value=0.0,
        int_value=0,
        string_value="",
        enum_value=0,
        nonzero_default=7,
    )
    for message in (absent, defaults):
        for name in names:
            assert _full_field_mask(message, name) == Mask()

    nondefaults = OptionalScalars(
        bool_value=True,
        bytes_value=b"x",
        double_value=1.0,
        int_value=1,
        string_value="x",
        enum_value=1,
        nonzero_default=0,
    )
    for name in names:
        assert _full_field_mask(nondefaults, name) is None


def test_full_reset_mask_distinguishes_absent_and_present_empty_messages() -> None:
    absent = Envelope()
    assert _full_field_mask(absent, "sample") == Mask()

    present = Envelope(sample=Sample())
    sample_mask = _full_field_mask(present, "sample")
    assert sample_mask is not None
    assert sample_mask.field_parts[FieldKey("child")] == Mask()
    assert sample_mask.field_parts[FieldKey("children")] == Mask()

    cleared = Envelope(sample=None)
    assert _full_field_mask(cleared, "sample") == Mask()


def test_full_reset_mask_python_none_clears_every_field_shape() -> None:
    cleared = Sample(
        count=None,
        optional_count=None,
        text=None,
        child=None,
        nums=None,
        children=None,
        labels=None,
        child_map=None,
    )
    for name in (
        "count",
        "optional_count",
        "text",
        "child",
        "nums",
        "children",
        "labels",
        "child_map",
    ):
        assert _full_field_mask(cleared, name) == Mask()


def test_full_reset_mask_lists_and_maps_match_go_reflection() -> None:
    empty = Sample(children=[], child_map={}, nums=[], labels={})
    for name in ("children", "child_map", "nums", "labels"):
        field_mask = _full_field_mask(empty, name)
        assert field_mask == Mask()
        assert field_mask.any is None

    scalar_values = Sample(nums=[0], labels={"zero": 0})
    assert _full_field_mask(scalar_values, "nums") is None
    assert _full_field_mask(scalar_values, "labels") is None

    messages = Sample(
        children=[Child(value=1), Child(note="set")],
        child_map={"value": Child(value=1), "note": Child(note="set")},
    )
    repeated = _full_field_mask(messages, "children")
    mapped = _full_field_mask(messages, "child_map")
    assert repeated is not None and repeated.any is not None
    assert mapped is not None and mapped.any is not None
    assert repeated.any.marshal() == "note,value"
    assert mapped.any.marshal() == "note,value"


def test_full_reset_mask_reflects_wkt_raw_state() -> None:
    assert Timestamp().get_full_update_reset_mask().marshal() == "nanos,seconds"
    assert Timestamp(seconds=1).get_full_update_reset_mask().marshal() == "nanos"
    assert Timestamp(nanos=1).get_full_update_reset_mask().marshal() == "seconds"
    assert Timestamp(seconds=1, nanos=1).get_full_update_reset_mask().marshal() == ""

    assert Duration().get_full_update_reset_mask().marshal() == "nanos,seconds"
    assert Duration(seconds=1, nanos=1).get_full_update_reset_mask().marshal() == ""
    assert ProtoAny().get_full_update_reset_mask().marshal() == "type_url,value"
    assert (
        ProtoAny(type_url="type.example/Message").get_full_update_reset_mask().marshal()
        == "value"
    )


def test_full_reset_mask_struct_value_list_value_empty_and_null() -> None:
    all_value_fields = (
        "bool_value,list_value,null_value,number_value,string_value,struct_value"
    )
    assert Value().get_full_update_reset_mask().marshal() == all_value_fields
    assert (
        Value(null_value=NullValue.NULL_VALUE).get_full_update_reset_mask().marshal()
        == all_value_fields
    )
    assert Value(number_value=1).get_full_update_reset_mask().marshal() == (
        "bool_value,list_value,null_value,string_value,struct_value"
    )
    for default_value in (
        Value(number_value=0),
        Value(string_value=""),
        Value(bool_value=False),
    ):
        assert default_value.get_full_update_reset_mask().marshal() == all_value_fields

    assert Struct().get_full_update_reset_mask().marshal() == "fields"
    assert Struct(fields=None).get_full_update_reset_mask().marshal() == "fields"
    assert Struct(fields={}).get_full_update_reset_mask().marshal() == "fields"
    assert (
        Struct(fields={"null": Value(null_value=NullValue.NULL_VALUE)})
        .get_full_update_reset_mask()
        .marshal()
        == f"fields.*.({all_value_fields})"
    )

    assert ListValue().get_full_update_reset_mask().marshal() == "values"
    assert ListValue(values=None).get_full_update_reset_mask().marshal() == "values"
    assert ListValue(values=[]).get_full_update_reset_mask().marshal() == "values"
    assert (
        ListValue(values=[Value(null_value=NullValue.NULL_VALUE)])
        .get_full_update_reset_mask()
        .marshal()
        == f"values.*.({all_value_fields})"
    )


def test_full_reset_mask_recursive_types_stop_at_absent_values() -> None:
    class Recursive(Message):
        __PROTO_FULL_NAME__ = "reset.mask.Recursive"

    recursive_codec = message_codec(lambda: Recursive)
    recursive = Field(
        "recursive_proto",
        "recursive_python",
        1,
        recursive_codec,
        json_name="recursiveJson",
    )
    repeated = Field(
        "repeated_proto",
        "repeated_python",
        2,
        recursive_codec,
        repeated=True,
        json_name="repeatedJson",
    )
    mapped = Field(
        "mapped_proto",
        "mapped_python",
        3,
        recursive_codec,
        map_key_codec=STRING,
        json_name="mappedJson",
    )
    Recursive.__FIELDS__ = (
        recursive,
        repeated,
        mapped,
    )

    assert Recursive().get_full_update_reset_mask().marshal() == (
        "mapped_proto,recursive_proto,repeated_proto"
    )
    assert Recursive(
        recursive_python=Recursive()
    ).get_full_update_reset_mask().marshal() == (
        "mapped_proto,recursive_proto.(mapped_proto,recursive_proto,repeated_proto),"
        "repeated_proto"
    )

    collection = Recursive(
        repeated_python=[Recursive()],
        mapped_python={"child": Recursive()},
    ).get_full_update_reset_mask()
    assert collection.field_parts[FieldKey("repeated_proto")].any is not None
    assert collection.field_parts[FieldKey("mapped_proto")].any is not None

    deep = Recursive()
    current = deep
    for _ in range(600):
        child = Recursive()
        current._values[recursive] = child
        current._present.add(recursive)
        current = child
    assert deep.get_full_update_reset_mask().marshal().count("recursive_proto") == 601

    cyclic = Recursive()
    cyclic._values[recursive] = cyclic
    cyclic._present.add(recursive)
    try:
        cyclic.get_full_update_reset_mask()
    except ValueError as error:
        assert str(error) == "reset mask recursion too deep"
    else:
        raise AssertionError("recursive reset-mask traversal had no depth limit")


def test_recursive_message_wire_depth_is_bounded() -> None:
    class Recursive(Message):
        __PROTO_FULL_NAME__ = "wire.depth.Recursive"
        __MAX_NESTING_DEPTH__ = 8

    recursive = Field("child", "child", 1, message_codec(lambda: Recursive))
    Recursive.__FIELDS__ = (recursive,)

    payload = b""
    for _ in range(9):
        writer = BinaryWriter()
        writer.write_tag(1, recursive.codec.wire_type)
        writer.write_bytes(payload)
        payload = writer.to_bytes()

    try:
        Recursive.FromString(payload)
    except DecodeError as error:
        assert str(error) == "protobuf message nesting exceeds the configured limit"
    else:
        raise AssertionError("recursive message decoding had no depth limit")

    nested = Recursive()
    for _ in range(8):
        nested = Recursive(child=nested)
    try:
        nested.SerializeToString()
    except EncodeError as error:
        assert str(error) == "protobuf message nesting exceeds the configured limit"
    else:
        raise AssertionError("recursive message encoding had no depth limit")

    cyclic = Recursive()
    cyclic._values[recursive] = cyclic
    cyclic._present.add(recursive)
    try:
        cyclic.SerializeToString()
    except EncodeError as error:
        assert str(error) == "protobuf message nesting exceeds the configured limit"
    else:
        raise AssertionError("cyclic message encoding had no depth limit")

    # The depth guards must be scoped to one operation, including failure paths.
    assert Recursive.FromString(b"").SerializeToString() == b""
    assert Recursive().SerializeToString() == b""
