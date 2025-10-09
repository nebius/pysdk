# type: ignore
import logging

import pytest


@pytest.mark.asyncio
async def test_get_instance_sync_in_async_no_loop() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, LoopError, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService(DiskServiceServicer):
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> disk_pb2.Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            # Return an Instance object as expected by the client
            ret = disk_pb2.Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
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
            options=[(INSECURE, True)],
            credentials=NoCredentials(),
        )
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))

        # Await response and metadata
        req.wait()
    except LoopError as e:
        assert (
            str(e) == "Synchronous call inside async context. Either use async/"
            "await or provide a safe and separate loop to run at the SDK "
            "initialization."
        )
    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_get_instance_sync_in_async_same_loop() -> None:
    from asyncio import (
        get_event_loop,
    )

    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, LoopError, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService(DiskServiceServicer):
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> disk_pb2.Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            # Return an Instance object as expected by the client
            ret = disk_pb2.Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
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
            options=[(INSECURE, True)],
            event_loop=get_event_loop(),
            credentials=NoCredentials(),
        )
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))

        # Await response and metadata
        req.wait()
    except LoopError as e:
        assert (
            str(e) == "Provided loop is equal to current thread's loop. Either use "
            "async/await or provide another loop at the SDK initialization."
        )
    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_get_instance_v2() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService(DiskServiceServicer):
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> disk_pb2.Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            await context.send_initial_metadata(
                (
                    ("x-request-id", "some-req-id"),
                    ("x-trace-id", "some-trace-id"),
                )
            )

            # Return an Instance object as expected by the client
            ret = disk_pb2.Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
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
            options=[(INSECURE, True)],
            credentials=NoCredentials(),
        )
        from nebius.api.nebius.compute.v1 import Disk, DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))

        # Await response and metadata
        ret = await req
        assert isinstance(ret, Disk)
        # Assertions to validate behavior
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_status_not_blocks_get_instance_v2() -> None:
    import grpc
    import grpc.aio
    from grpc import StatusCode

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService(DiskServiceServicer):
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> disk_pb2.Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            await context.send_initial_metadata(
                (
                    ("x-request-id", "some-req-id"),
                    ("x-trace-id", "some-trace-id"),
                )
            )

            # Return an Instance object as expected by the client
            ret = disk_pb2.Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
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
            domain=address, options=[(INSECURE, True)], credentials=NoCredentials()
        )
        from nebius.api.nebius.compute.v1 import Disk, DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))

        status_coro = req.status()
        # Await response and metadata
        ret = await req
        assert isinstance(ret, Disk)
        status = await status_coro
        assert status.code == StatusCode.OK
        # Assertions to validate behavior
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)
