"""Behavioral goldens that must survive the direct-message revamp."""

from __future__ import annotations

from typing import Any

from nebius.api.google.protobuf import Timestamp
from nebius.api.nebius import api_service_name
from nebius.api.nebius.common.v1 import ResourceMetadata
from nebius.api.nebius.compute.v1 import (
    DiskServiceClient,
    DiskSpec,
    UpdateDiskRequest,
)


def _serialize(message: Any) -> bytes:
    return message.SerializeToString(deterministic=True)


def _has_field(message: Any, name: str) -> bool:
    return bool(message.HasField(name))


def _varint(value: int) -> bytes:
    encoded = bytearray()
    while value > 0x7F:
        encoded.append((value & 0x7F) | 0x80)
        value >>= 7
    encoded.append(value)
    return bytes(encoded)


def test_identity_equality_and_hash_are_preserved() -> None:
    left = DiskSpec()
    right = DiskSpec()
    assert left != right
    assert left == left
    assert isinstance(hash(left), int)


def test_nested_read_and_mutation_reset_mask_golden() -> None:
    request = UpdateDiskRequest()
    assert str(request.get_mask()) == "Mask()"

    metadata = request.metadata
    assert str(request.get_mask()) == "Mask(metadata)"
    assert not _has_field(request, "metadata")

    metadata.id = "disk-id"
    assert str(request.get_mask()) == "Mask(metadata)"
    assert _has_field(request, "metadata")


def test_message_assignment_copies_instead_of_aliasing() -> None:
    metadata = ResourceMetadata(id="initial")
    request = UpdateDiskRequest(metadata=metadata)
    metadata.id = "changed"
    assert request.metadata.id == "initial"


def test_wkt_convenience_read_preserves_raw_nanos_and_unknowns() -> None:
    assert ResourceMetadata().created_at is None

    raw_timestamp = (
        Timestamp(seconds=7, nanos=123).SerializeToString(deterministic=True)
        + b"\x98\x06\x2a"
    )
    created_at = next(
        field
        for field in ResourceMetadata.__FIELDS__
        if field.proto_name == "created_at"
    )
    wire = (
        _varint((created_at.number << 3) | 2)
        + _varint(len(raw_timestamp))
        + raw_timestamp
    )
    wrapped = ResourceMetadata.FromString(wire)

    assert wrapped.created_at is not None
    assert _serialize(wrapped) == wire


def test_exported_option_extension_lookup_shape() -> None:
    descriptor = DiskServiceClient.__PB2_DESCRIPTOR__
    assert descriptor.full_name == "nebius.compute.v1.DiskService"
    assert descriptor.GetOptions().Extensions[api_service_name] == "compute"
