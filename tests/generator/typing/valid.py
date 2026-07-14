from typing_extensions import assert_type

from nebius.aio.request import Request
from nebius.api.nebius.compute.v1 import (
    Disk,
    DiskServiceClient,
    DiskSpec,
    GetDiskRequest,
)


def size_gibibytes(spec: DiskSpec) -> int | None:
    return spec.size_gibibytes


disk = DiskSpec(
    size_gibibytes=16,
    type=DiskSpec.DiskType.NETWORK_SSD,
)
size_gibibytes(disk)


def request_type(client: DiskServiceClient) -> None:
    request = client.get(GetDiskRequest(id="example"))
    assert_type(request, Request[GetDiskRequest, Disk])


async def result_type(client: DiskServiceClient) -> None:
    result = await client.get(GetDiskRequest(id="example"))
    assert_type(result, Disk)
