def test_repeated_messages_keep_identity_and_nested_mutations() -> None:
    from nebius.api.nebius.common.v1 import ResourceMetadata
    from nebius.api.nebius.compute.v1 import Disk, ListDisksResponse

    direct_item = Disk(metadata=ResourceMetadata(name="before"))
    response = ListDisksResponse(items=[direct_item])
    assert response.items[0] is direct_item

    decoded = ListDisksResponse.FromString(response.SerializeToString())
    decoded_item = decoded.items[0]
    assert decoded.items[0] is decoded_item
    decoded_item.metadata.name = "after"

    round_trip = ListDisksResponse.FromString(decoded.SerializeToString())
    assert round_trip.items[0].metadata.name == "after"


def test_singular_and_repeated_properties_keep_stable_references() -> None:
    from nebius.api.nebius.compute.v1 import Disk, ListDisksResponse

    disk = Disk()
    metadata = disk.metadata
    assert disk.metadata is metadata
    metadata.name = "kept"
    assert Disk.FromString(disk.SerializeToString()).metadata.name == "kept"

    response = ListDisksResponse()
    items = response.items
    assert response.items is items
    items.append(Disk(metadata=metadata))
    assert len(ListDisksResponse.FromString(response.SerializeToString()).items) == 1


def test_message_maps_keep_identity_and_nested_mutations() -> None:
    from nebius.api.nebius.compute.v1 import InstanceStatus, NVLInstanceGroupStatus

    direct_info = NVLInstanceGroupStatus.InstanceInfo(
        instance_state=InstanceStatus.InstanceState.STARTING
    )
    status = NVLInstanceGroupStatus(instances={"instance": direct_info})
    instances = status.instances
    assert status.instances is instances
    assert status.instances["instance"] is direct_info

    decoded = NVLInstanceGroupStatus.FromString(status.SerializeToString())
    decoded_info = decoded.instances["instance"]
    assert decoded.instances["instance"] is decoded_info
    decoded_info.instance_state = InstanceStatus.InstanceState.RUNNING

    round_trip = NVLInstanceGroupStatus.FromString(decoded.SerializeToString())
    assert (
        round_trip.instances["instance"].instance_state
        is InstanceStatus.InstanceState.RUNNING
    )


def test_message_fields_reject_incompatible_direct_types() -> None:
    import pytest

    from nebius.api.nebius.compute.v1 import (
        Disk,
        DiskSpec,
        ListDisksResponse,
        NVLInstanceGroupStatus,
    )

    with pytest.raises(TypeError, match="Wrong message type"):
        Disk(metadata=DiskSpec(size_gibibytes=8))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Wrong message type"):
        ListDisksResponse(items=[DiskSpec()])  # type: ignore[list-item]
    with pytest.raises(TypeError, match="Wrong message type"):
        NVLInstanceGroupStatus(instances={"instance": DiskSpec()})  # type: ignore[dict-item]

    with pytest.raises(TypeError, match="Wrong message type"):
        DiskSpec().CopyFrom(Disk())
    with pytest.raises(TypeError, match="Wrong message type"):
        DiskSpec().MergeFrom(Disk())
