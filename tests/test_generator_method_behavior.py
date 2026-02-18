from google.protobuf.descriptor_pb2 import MethodOptions

from nebius.api.nebius import annotations_pb2
from nebius.base.protos.compiler.generators import _should_add_reset_mask


class _FakeDescriptor:
    def __init__(self, options: MethodOptions) -> None:
        self.options = options


class _FakeMethod:
    def __init__(self, name: str, options: MethodOptions) -> None:
        self.name = name
        self.descriptor = _FakeDescriptor(options)


def _fake_method(name: str, method_behaviors: list[int] | None = None) -> _FakeMethod:
    options = MethodOptions()
    if method_behaviors:
        options.Extensions[annotations_pb2.method_behavior].extend(method_behaviors)
    return _FakeMethod(name, options)


def test_reset_mask_defaults_to_update_method_name_when_not_set() -> None:
    assert _should_add_reset_mask(_fake_method("Update")) is True
    assert _should_add_reset_mask(_fake_method("Patch")) is False


def test_reset_mask_uses_method_behavior_updater_when_set() -> None:
    assert (
        _should_add_reset_mask(
            _fake_method("Patch", [annotations_pb2.METHOD_UPDATER]),
        )
        is True
    )
    assert (
        _should_add_reset_mask(
            _fake_method(
                "Update",
                [annotations_pb2.METHOD_PAGINATED],
            ),
        )
        is False
    )
