# type: ignore
import logging

import pytest


@pytest.mark.asyncio
async def test_update_instance_v2() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.common.v1.operation_pb2 as operation_pb2
    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
        UpdateDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE
    from nebius.base.version import version as sdk_version

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService(DiskServiceServicer):
        async def Update(  # noqa: N802 — GRPC method
            self,
            request: UpdateDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> operation_pb2.Operation:
            assert request.metadata.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""
            got_mask = md.get("x-resetmask", "")
            assert (
                "metadata.(created_at.(nanos,seconds),labels.*,name,parent_id,"
                + "resource_version,updated_at.(nanos,seconds)),spec.("
                in got_mask
            )
            ua = md.get("user-agent", "")
            assert ua.startswith(
                f"a b c test nebius-python-sdk/{sdk_version} (python/3."
            )
            assert ua.endswith(" x y z")

            await context.send_initial_metadata(
                (
                    ("x-request-id", "some-req-id"),
                    ("x-trace-id", "some-trace-id"),
                )
            )

            ret = operation_pb2.Operation()
            return ret

    # Randomly assign an IPv6 address and port for the server
    srv = grpc.aio.server()
    assert isinstance(srv, grpc.aio.Server)
    port = srv.add_insecure_port("[::]:0")
    add_DiskServiceServicer_to_server(MockInstanceService(), srv)
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address,
            options=[
                (INSECURE, True),
                ("grpc.primary_user_agent", "a"),
                ("grpc.primary_user_agent", "b"),
                ("grpc.secondary_user_agent", "x"),
                ("grpc.secondary_user_agent", "y"),
            ],
            address_options={
                f"compute.localhost:{port}": [
                    ("grpc.primary_user_agent", "c"),
                    ("grpc.secondary_user_agent", "z"),
                ]
            },
            credentials=NoCredentials(),
            user_agent_prefix="test",
        )
        from nebius.aio.operation import Operation
        from nebius.api.nebius.compute.v1 import (
            DiskServiceClient,
            GetDiskRequest,
            UpdateDiskRequest,
        )

        client = DiskServiceClient(channel)
        upd = UpdateDiskRequest()
        upd.metadata.id = "foo-bar"
        req = client.update(upd)

        # Await response and metadata
        ret = await req
        assert isinstance(ret, Operation)
    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_update_list() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.common.v1.operation_pb2 as operation_pb2
    import nebius.api.nebius.compute.v1.instance_pb2 as instance_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1.instance_service_pb2 import (
        GetInstanceRequest,
        UpdateInstanceRequest,
    )
    from nebius.api.nebius.compute.v1.instance_service_pb2_grpc import (
        InstanceServiceServicer,
        add_InstanceServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService(InstanceServiceServicer):
        async def Update(  # noqa: N802 — GRPC method
            self,
            request: UpdateInstanceRequest,
            context: grpc.aio.ServicerContext[
                GetInstanceRequest, instance_pb2.Instance
            ],
        ) -> operation_pb2.Operation:
            assert request.metadata.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""
            mask = md.get("x-resetmask", "")
            assert (
                "metadata.("
                "created_at.(nanos,seconds),labels.*,name,parent_id,resource_version,"
                "updated_at.(nanos,seconds)"
                "),"
                "spec.(" in mask
            )

            await context.send_initial_metadata(
                (
                    ("x-request-id", "some-req-id"),
                    ("x-trace-id", "some-trace-id"),
                )
            )

            ret = operation_pb2.Operation()
            return ret

    # Randomly assign an IPv6 address and port for the server
    srv = grpc.aio.server()
    assert isinstance(srv, grpc.aio.Server)
    port = srv.add_insecure_port("[::]:0")
    add_InstanceServiceServicer_to_server(MockInstanceService(), srv)
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address, options=[(INSECURE, True)], credentials=NoCredentials()
        )
        from nebius.aio.operation import Operation
        from nebius.api.nebius.compute.v1 import (
            AttachedFilesystemSpec,
            ExistingFilesystem,
            InstanceServiceClient,
            UpdateInstanceRequest,
        )

        client = InstanceServiceClient(channel)
        upd = UpdateInstanceRequest()
        upd.metadata.id = "foo-bar"
        upd.spec.filesystems = [
            AttachedFilesystemSpec(
                attach_mode=AttachedFilesystemSpec.AttachMode.READ_WRITE,
                mount_tag="/mnt/foo-bar",
                existing_filesystem=ExistingFilesystem(
                    id="foo-bar",
                ),
            )
        ]
        upd.spec.filesystems = []
        req = client.update(upd)

        # Await response and metadata
        ret = await req
        assert isinstance(ret, Operation)
    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)
