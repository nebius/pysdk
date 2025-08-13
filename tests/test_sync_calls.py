# type: ignore
import logging


def test_get_instance_sync() -> None:
    from asyncio import (
        Event,
        new_event_loop,
        set_event_loop,
    )
    from concurrent.futures import Future
    from threading import Thread

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

            # Return an Instance object as expected by the client
            ret = disk_pb2.Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
            return ret

    def server_thread(port_future: Future[int], stop_event: Event) -> None:
        # Create a new event loop for the thread
        loop = new_event_loop()
        set_event_loop(loop)

        async def start_server():
            # Create the gRPC server
            srv = grpc.aio.server()
            add_DiskServiceServicer_to_server(MockInstanceService(), srv)

            # Bind to a random available port
            port = srv.add_insecure_port("[::]:0")
            port_future.set_result(port)  # Pass the port back to the main thread

            await srv.start()  # Start the server
            await stop_event.wait()
            await srv.stop(0)

        try:
            loop.run_until_complete(start_server())
        finally:
            loop.close()

    # Randomly assign an IPv6 address and port for the server

    # Future to share the port between threads
    port_future = Future[int]()
    stop_event = Event()

    # Start the server thread
    worker = Thread(
        target=server_thread,
        args=(
            port_future,
            stop_event,
        ),
        daemon=True,
    )
    worker.start()

    # Wait for the port to be set
    port = port_future.result()

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
        ret = req.wait()

        # Assertions to validate behavior
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"

    finally:
        # Clean up
        if channel is not None:
            channel.sync_close()
        stop_event.set()


def test_get_instance_timeout_sync() -> None:
    from asyncio import (
        Event,
        new_event_loop,
        set_event_loop,
    )
    from concurrent.futures import Future
    from threading import Thread

    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.service_error import RequestError
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
            from asyncio import sleep

            await sleep(2)

            # Return an Instance object as expected by the client
            ret = disk_pb2.Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
            return ret

    def server_thread(port_future: Future[int], stop_event: Event) -> None:
        # Create a new event loop for the thread
        loop = new_event_loop()
        set_event_loop(loop)

        async def start_server():
            # Create the gRPC server
            srv = grpc.aio.server()
            add_DiskServiceServicer_to_server(MockInstanceService(), srv)

            # Bind to a random available port
            port = srv.add_insecure_port("[::]:0")
            port_future.set_result(port)  # Pass the port back to the main thread

            await srv.start()  # Start the server
            await stop_event.wait()
            await srv.stop(0)

        try:
            loop.run_until_complete(start_server())
        finally:
            loop.close()

    # Randomly assign an IPv6 address and port for the server

    # Future to share the port between threads
    port_future = Future[int]()
    stop_event = Event()

    # Start the server thread
    worker = Thread(
        target=server_thread,
        args=(
            port_future,
            stop_event,
        ),
        daemon=True,
    )
    worker.start()

    # Wait for the port to be set
    port = port_future.result()

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
        req = client.get(GetDiskRequest(id="foo-bar"), timeout=0.1)

        try:
            # Await response and metadata
            req.wait()
        except RequestError as e:
            assert str(e) == "Request error DEADLINE_EXCEEDED: Deadline Exceeded"
            assert e.status.code == grpc.StatusCode.DEADLINE_EXCEEDED

    finally:
        # Clean up
        if channel is not None:
            channel.sync_close()
        stop_event.set()
