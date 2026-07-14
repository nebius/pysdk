"""Direct generated enum behavior."""

from __future__ import annotations

import copy

from nebius.base.protos.pb_enum import Enum


class State(Enum):
    __PROTO_FULL_NAME__ = "direct.test.State"
    UNSPECIFIED = 0
    READY = 1
    ALSO_READY = 1


def test_direct_enum_known_alias_and_integer_behavior() -> None:
    assert State.READY is State.ALSO_READY
    assert State(1) is State.READY
    assert State.READY == 1
    assert int(State.READY) == 1
    assert list(State) == [State.UNSPECIFIED, State.READY]


def test_direct_open_enum_preserves_unknown_numbers() -> None:
    unknown = State(37)
    assert int(unknown) == 37
    assert unknown.name == "UNRECOGNIZED_37"
    assert State(37) is not unknown
    assert copy.copy(unknown) == unknown
    assert copy.deepcopy(unknown) == unknown


def test_direct_enum_prefers_registry_descriptor_facade() -> None:
    marker = object()
    State.__PROTO_DESCRIPTOR__ = lambda: marker
    try:
        assert State.get_descriptor() is marker
    finally:
        State.__PROTO_DESCRIPTOR__ = None
