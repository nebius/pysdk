# type:ignore
import logging
import tracemalloc

import pytest

tracemalloc.start()


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


@pytest.mark.asyncio
async def test_credentials_updater() -> None:
    from asyncio import sleep

    import grpc
    import grpc.aio
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.common.v1.operation_pb2 as operation_pb2
    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
        UpdateDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc import (
        TokenExchangeService,
        add_TokenExchangeServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_service_pb2 import (
        CreateTokenResponse,
        ExchangeTokenRequest,
    )
    from nebius.base.options import INSECURE
    from nebius.base.service_account.service_account import ServiceAccount

    stub_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
    )

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    call = 0

    class MockTokenExchangeService(TokenExchangeService):
        async def Exchange(  # noqa: N802 — GRPC method
            self,
            request: ExchangeTokenRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> CreateTokenResponse:
            nonlocal call
            if call == 0:
                call += 1
                await sleep(6)
            ret = CreateTokenResponse(
                access_token="foo-bar",
                expires_in=3600,
                issued_token_type="Bearer",
                token_type="Bearer",
            )
            return ret

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
    add_TokenExchangeServiceServicer_to_server(MockTokenExchangeService(), srv)
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address,
            options=[(INSECURE, True)],
            credentials=ServiceAccount(
                private_key=stub_key,
                public_key_id="public-key-test",
                service_account_id="service-account-test",
            ),
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
async def test_credentials_updater_sync() -> None:
    from asyncio import sleep

    import grpc
    import grpc.aio
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.common.v1.operation_pb2 as operation_pb2
    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
        UpdateDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc import (
        TokenExchangeService,
        add_TokenExchangeServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_service_pb2 import (
        CreateTokenResponse,
        ExchangeTokenRequest,
    )
    from nebius.base.options import INSECURE
    from nebius.base.service_account.service_account import ServiceAccount

    stub_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
    )

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    call = 0

    class MockTokenExchangeService(TokenExchangeService):
        async def Exchange(  # noqa: N802 — GRPC method
            self,
            request: ExchangeTokenRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> CreateTokenResponse:
            nonlocal call
            if call == 0:
                call += 1
                await sleep(6)
            ret = CreateTokenResponse(
                access_token="foo-bar",
                expires_in=3600,
                issued_token_type="Bearer",
                token_type="Bearer",
            )
            return ret

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
    add_TokenExchangeServiceServicer_to_server(MockTokenExchangeService(), srv)
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address,
            options=[(INSECURE, True)],
            credentials=ServiceAccount(
                private_key=stub_key,
                public_key_id="public-key-test",
                service_account_id="service-account-test",
            ),
        )
        from nebius.aio.authorization.options import options_to_metadata
        from nebius.aio.operation import Operation
        from nebius.aio.token.renewable import (
            OPTION_RENEW_REQUEST_TIMEOUT,
            OPTION_RENEW_REQUIRED,
            OPTION_RENEW_SYNCHRONOUS,
        )
        from nebius.api.nebius.compute.v1 import (
            DiskServiceClient,
            GetDiskRequest,
            UpdateDiskRequest,
        )

        client = DiskServiceClient(channel)
        upd = UpdateDiskRequest()
        upd.metadata.id = "foo-bar"
        req = client.update(
            upd,
            metadata=options_to_metadata(
                {
                    OPTION_RENEW_REQUIRED: "1",
                    OPTION_RENEW_SYNCHRONOUS: "1",
                    OPTION_RENEW_REQUEST_TIMEOUT: ".1",
                }
            ),
        )

        # Await response and metadata
        ret = await req
        assert isinstance(ret, Operation)
    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


def test_load_config_from_home(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
"""
        )
    # Load the configuration
    config = Config("foo")
    assert config.parent_id == "project-e00some-id"


@pytest.mark.asyncio
async def test_load_config_env_token(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.base import ChannelBase
    from nebius.aio.cli_config import Config
    from nebius.aio.token.static import EnvBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NEBIUS_IAM_TOKEN", "my-token")

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
"""
        )
    # Load the configuration
    config = Config("foo")
    fut = Future[ChannelBase]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, EnvBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


@pytest.mark.asyncio
async def test_load_config_token_file(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.base import ChannelBase
    from nebius.aio.cli_config import Config
    from nebius.aio.token.file import Bearer as FileBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("NEBIUS_IAM_TOKEN", raising=False)

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        token-file: ~/token.txt
"""
        )
    with open(tmp_path / "token.txt", "w+") as f:
        f.write("my-token")
    # Load the configuration
    config = Config("foo")
    fut = Future[ChannelBase]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, FileBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


@pytest.mark.asyncio
async def test_load_config_no_env(tmp_path, monkeypatch) -> None:
    from asyncio import Future

    from nebius.aio.base import ChannelBase
    from nebius.aio.cli_config import Config
    from nebius.aio.token.file import Bearer as FileBearer

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NEBIUS_IAM_TOKEN", "wrong-token")

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
        token-file: ~/token.txt
"""
        )
    with open(tmp_path / "token.txt", "w+") as f:
        f.write("my-token")
    # Load the configuration
    config = Config("foo", no_env=True)
    fut = Future[ChannelBase]()
    tok = config.get_credentials(fut)
    assert isinstance(tok, FileBearer)
    receiver = tok.receiver()
    tok = await receiver.fetch()
    assert tok.token == "my-token"


def test_load_config_other_profile(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
    test:
        endpoint: test-endpoint.net
        parent-id: project-e00test-id
"""
        )
    # Load the configuration
    config = Config("foo", profile="test")
    assert config.parent_id == "project-e00test-id"


def test_load_config_no_project(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    with open(nebius_dir / "config.yaml", "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
"""
        )
    # Load the configuration
    config = Config("foo")
    try:
        config.parent_id
    except Exception as e:
        assert str(e) == "Missing parent-id in the profile."


def test_load_config_from_home_fail(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / ".nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(tmp_path))

    try:
        Config("foo")
    except FileNotFoundError as e:
        assert str(e).startswith("Config file ")
        assert str(e).endswith("/.nebius/config.yaml not found.")


def test_load_config_from_other_place(tmp_path, monkeypatch) -> None:
    from nebius.aio.cli_config import Config

    nebius_dir = tmp_path / "home/.nebius"
    nebius_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_path / "config.yaml"

    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    with open(tmp_file, "w+") as f:
        f.write(
            """
default: prod
profiles:
    prod:
        endpoint: my-endpoint.net
        parent-id: project-e00some-id
"""
        )
    # Load the configuration
    config = Config("foo", config_file=str(tmp_file))
    assert config.parent_id == "project-e00some-id"


@pytest.mark.asyncio
async def test_credentials_updater_sync_error() -> None:
    import grpc
    import grpc.aio
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.common.v1.operation_pb2 as operation_pb2
    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel
    from nebius.aio.service_error import RequestError, RequestStatusExtended
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
        UpdateDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        add_DiskServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_exchange_service_pb2_grpc import (
        TokenExchangeService,
        add_TokenExchangeServiceServicer_to_server,
    )
    from nebius.api.nebius.iam.v1.token_service_pb2 import (
        CreateTokenResponse,
        ExchangeTokenRequest,
    )
    from nebius.base.options import INSECURE
    from nebius.base.service_account.service_account import ServiceAccount

    stub_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=1024,
    )

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    class MockTokenExchangeService(TokenExchangeService):
        async def Exchange(  # noqa: N802 — GRPC method
            self,
            request: ExchangeTokenRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> CreateTokenResponse:
            await context.send_initial_metadata(
                (
                    ("x-request-id", "some-req-id"),
                    ("x-trace-id", "some-trace-id"),
                )
            )

            import nebius.api.nebius.common.v1.error_pb2 as error_pb2
            from nebius.base._service_error import trailing_metadata_of_errors

            quota_violation = error_pb2.QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
            service_error = error_pb2.ServiceError(
                service="example.service",
                code="test failure",
                quota_failure=quota_failure,
            )

            await context.abort(
                code=grpc.StatusCode.RESOURCE_EXHAUSTED,
                details="test exhausted",
                trailing_metadata=trailing_metadata_of_errors(
                    service_error,
                    status_code=grpc.StatusCode.RESOURCE_EXHAUSTED.value,
                    status_message="test exhausted",
                ),
            )

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
    add_TokenExchangeServiceServicer_to_server(MockTokenExchangeService(), srv)
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address,
            options=[(INSECURE, True)],
            credentials=ServiceAccount(
                private_key=stub_key,
                public_key_id="public-key-test",
                service_account_id="service-account-test",
            ),
        )
        from nebius.aio.authorization.options import options_to_metadata
        from nebius.aio.token.renewable import (
            OPTION_RENEW_REQUEST_TIMEOUT,
            OPTION_RENEW_REQUIRED,
            OPTION_RENEW_SYNCHRONOUS,
        )
        from nebius.api.nebius.compute.v1 import (
            DiskServiceClient,
            GetDiskRequest,
            UpdateDiskRequest,
        )

        client = DiskServiceClient(channel)
        upd = UpdateDiskRequest()
        upd.metadata.id = "foo-bar"
        req = client.update(
            upd,
            metadata=options_to_metadata(
                {
                    OPTION_RENEW_REQUIRED: "1",
                    OPTION_RENEW_SYNCHRONOUS: "1",
                    OPTION_RENEW_REQUEST_TIMEOUT: ".1",
                }
            ),
        )

        # Await response and metadata
        await req
    except RequestError as e:
        assert (
            str(e) == "Request error RESOURCE_EXHAUSTED: test exhausted; "
            "request_id: some-req-id; trace_id: some-trace-id; Caused by error: "
            "1. test failure in service example.service quota failure, violations:"
            "  test_quota 69 of 42: testing quota failure;"
        )
        assert e.status.request_id == "some-req-id"
        assert e.status.trace_id == "some-trace-id"
        assert isinstance(e.status, RequestStatusExtended)
        assert len(e.status.service_errors) == 1
        assert e.status.service_errors[0].quota_failure is not None
    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


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
            assert (
                md.get("x-resetmask", "")
                == "metadata.(created_at.(nanos,seconds),labels.*,name,parent_id,"
                + "resource_version,updated_at.(nanos,seconds)),spec.(block_size_bytes"
                + ",size_bytes,size_gibibytes,size_kibibytes,size_mebibytes,"
                + "source_image_family,source_image_id,type)"
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


@pytest.mark.asyncio
async def test_get_instance_error() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.request_status import UnfinishedRequestStatus
    from nebius.aio.service_error import RequestError, RequestStatusExtended
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

            import nebius.api.nebius.common.v1.error_pb2 as error_pb2
            from nebius.base._service_error import trailing_metadata_of_errors

            quota_violation = error_pb2.QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
            service_error = error_pb2.ServiceError(
                service="example.service",
                code="test failure",
                quota_failure=quota_failure,
            )

            await context.abort(
                code=grpc.StatusCode.RESOURCE_EXHAUSTED,
                details="test exhausted",
                trailing_metadata=trailing_metadata_of_errors(
                    service_error,
                    status_code=grpc.StatusCode.RESOURCE_EXHAUSTED.value,
                    status_message="test exhausted",
                ),
            )

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
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))
        status = req.current_status()
        assert status == UnfinishedRequestStatus.INITIALIZED

        # Await response and metadata
        await req
    except RequestError as e:
        assert (
            str(e) == "Request error RESOURCE_EXHAUSTED: test exhausted; "
            "request_id: some-req-id; trace_id: some-trace-id; Caused by error: "
            "1. test failure in service example.service quota failure, violations:"
            "  test_quota 69 of 42: testing quota failure;"
        )
        assert e.status.request_id == "some-req-id"
        assert e.status.trace_id == "some-trace-id"
        status = req.current_status()
        assert isinstance(status, RequestStatusExtended)
        assert len(status.service_errors) == 1
        assert status.service_errors[0].quota_failure is not None

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_get_instance_retry() -> None:
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

    counter = 0

    # Define a mock server class
    class MockInstanceService(DiskServiceServicer):
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, disk_pb2.Disk],
        ) -> disk_pb2.Disk:
            nonlocal counter
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

            import nebius.api.nebius.common.v1.error_pb2 as error_pb2
            from nebius.base._service_error import trailing_metadata_of_errors

            if counter == 0:
                counter = 1

                quota_violation = error_pb2.QuotaFailure.Violation(
                    quota="test_quota",
                    message="testing quota failure",
                    limit="42",
                    requested="69",
                )
                quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
                service_error = error_pb2.ServiceError(
                    service="example.service",
                    code="test failure",
                    quota_failure=quota_failure,
                    retry_type=error_pb2.ServiceError.RetryType.CALL,
                )

                await context.abort(
                    code=grpc.StatusCode.RESOURCE_EXHAUSTED,
                    details="test exhausted",
                    trailing_metadata=trailing_metadata_of_errors(
                        service_error,
                        status_code=grpc.StatusCode.RESOURCE_EXHAUSTED.value,
                        status_message="test exhausted",
                    ),
                )
            else:
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
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))

        # Await response and metadata
        res = await req
        assert res.metadata.name == "MockDisk"
    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_metadata_at_error() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.request_status import UnfinishedRequestStatus
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

            import nebius.api.nebius.common.v1.error_pb2 as error_pb2
            from nebius.base._service_error import trailing_metadata_of_errors

            quota_violation = error_pb2.QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
            service_error = error_pb2.ServiceError(
                service="example.service",
                code="test failure",
                quota_failure=quota_failure,
            )

            await context.abort(
                code=grpc.StatusCode.RESOURCE_EXHAUSTED,
                details="test exhausted",
                trailing_metadata=trailing_metadata_of_errors(
                    service_error,
                    status_code=grpc.StatusCode.RESOURCE_EXHAUSTED.value,
                    status_message="test exhausted",
                ),
            )

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
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))
        status = req.current_status()
        assert status == UnfinishedRequestStatus.INITIALIZED

        md = await req.initial_metadata()
        assert len(md) == 2
        assert md["x-request-id"] == ["some-req-id"]
        assert md["x-trace-id"] == ["some-trace-id"]

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_status_at_error() -> None:
    import grpc
    import grpc.aio
    from grpc import StatusCode

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.request_status import UnfinishedRequestStatus
    from nebius.aio.service_error import RequestStatusExtended
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

            import nebius.api.nebius.common.v1.error_pb2 as error_pb2
            from nebius.base._service_error import trailing_metadata_of_errors

            quota_violation = error_pb2.QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
            service_error = error_pb2.ServiceError(
                service="example.service",
                code="test failure",
                quota_failure=quota_failure,
            )

            await context.abort(
                code=StatusCode.RESOURCE_EXHAUSTED,
                details="test exhausted",
                trailing_metadata=trailing_metadata_of_errors(
                    service_error,
                    status_code=StatusCode.RESOURCE_EXHAUSTED.value,
                    status_message="test exhausted",
                ),
            )

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
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))
        status = req.current_status()
        assert status == UnfinishedRequestStatus.INITIALIZED

        status = await req.status()
        status2 = req.current_status()
        assert isinstance(status, RequestStatusExtended)
        assert status == status2
        assert status.code == StatusCode.RESOURCE_EXHAUSTED

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_status_does_not_block_failed_call() -> None:
    import grpc
    import grpc.aio
    from grpc import StatusCode

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.service_error import RequestStatusExtended
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

            import nebius.api.nebius.common.v1.error_pb2 as error_pb2
            from nebius.base._service_error import trailing_metadata_of_errors

            quota_violation = error_pb2.QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
            service_error = error_pb2.ServiceError(
                service="example.service",
                code="test failure",
                quota_failure=quota_failure,
            )

            await context.abort(
                code=StatusCode.RESOURCE_EXHAUSTED,
                details="test exhausted",
                trailing_metadata=trailing_metadata_of_errors(
                    service_error,
                    status_code=StatusCode.RESOURCE_EXHAUSTED.value,
                    status_message="test exhausted",
                ),
            )

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
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))
        status_coro = req.status()

        exc: BaseException | None = None
        try:
            await req
        except Exception as e:
            exc = e
        assert exc is not None
        status = await status_coro

        assert isinstance(status, RequestStatusExtended)
        assert status.code == StatusCode.RESOURCE_EXHAUSTED

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_request_id_at_error() -> None:
    import grpc
    import grpc.aio
    from grpc import StatusCode

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.request_status import UnfinishedRequestStatus
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

            import nebius.api.nebius.common.v1.error_pb2 as error_pb2
            from nebius.base._service_error import trailing_metadata_of_errors

            quota_violation = error_pb2.QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
            service_error = error_pb2.ServiceError(
                service="example.service",
                code="test failure",
                quota_failure=quota_failure,
            )

            await context.abort(
                code=StatusCode.RESOURCE_EXHAUSTED,
                details="test exhausted",
                trailing_metadata=trailing_metadata_of_errors(
                    service_error,
                    status_code=StatusCode.RESOURCE_EXHAUSTED.value,
                    status_message="test exhausted",
                ),
            )

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
        from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest

        client = DiskServiceClient(channel)
        req = client.get(GetDiskRequest(id="foo-bar"))
        status = req.current_status()
        assert status == UnfinishedRequestStatus.INITIALIZED

        req_id = await req.request_id()
        trace_id = await req.trace_id()
        assert req_id == "some-req-id"
        assert trace_id == "some-trace-id"

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_get_instance() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._interceptor import InterceptedUnaryUnaryCall as UnaryUnaryCall
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        DiskServiceStub,
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
            domain=address, options=[(INSECURE, True)], credentials=NoCredentials()
        )
        stub = DiskServiceStub(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = stub.Get(req)
        assert isinstance(call, UnaryUnaryCall)

        # Await response and metadata
        ret = await call
        assert isinstance(ret, disk_pb2.Disk)
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        code = await call.code()
        details = await call.details()

        # Assertions to validate behavior
        assert ret.HasField("metadata")
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"
        assert code == grpc.StatusCode.OK
        assert details == ""
        assert mdi is not None and len(mdi) == 0
        assert mdt is not None and len(mdt) == 0

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_get_instance_timeout_change() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._interceptor import InterceptedUnaryUnaryCall as UnaryUnaryCall
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel
    from nebius.aio.token.static import Bearer
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        DiskServiceStub,
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
            domain=address, options=[(INSECURE, True)], credentials=Bearer("abc")
        )
        stub = DiskServiceStub(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = stub.Get(req, timeout=1)
        assert isinstance(call, UnaryUnaryCall)

        # Await response and metadata
        ret = await call
        assert isinstance(ret, disk_pb2.Disk)
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        code = await call.code()
        details = await call.details()

        # Assertions to validate behavior
        assert ret.HasField("metadata")
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"
        assert code == grpc.StatusCode.OK
        assert details == ""
        assert mdi is not None and len(mdi) == 0
        assert mdt is not None and len(mdt) == 0

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_get_error() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._interceptor import InterceptedUnaryUnaryCall as UnaryUnaryCall
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.common.v1.error_pb2 as error_pb2
    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        DiskServiceStub,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base._service_error import trailing_metadata_of_errors
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

            quota_violation = error_pb2.QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = error_pb2.QuotaFailure(violations=[quota_violation])
            service_error = error_pb2.ServiceError(
                service="example.service",
                code="test failure",
                quota_failure=quota_failure,
            )

            await context.abort(
                code=grpc.StatusCode.RESOURCE_EXHAUSTED,
                details="test exhausted",
                trailing_metadata=trailing_metadata_of_errors(service_error),
            )

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
        stub = DiskServiceStub(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = stub.Get(req)
        assert isinstance(call, UnaryUnaryCall)

        # Await response and metadata
        try:
            mdi = await call.initial_metadata()
            mdt = await call.trailing_metadata()
            code = await call.code()
            details = await call.details()
            ret = await call
            assert isinstance(ret, disk_pb2.Disk)

            # Assertions to validate behavior
            assert ret.metadata.id == "foo-bar"
            assert ret.metadata.name == "MockDisk"
            assert code == grpc.StatusCode.OK
            assert details == ""
            assert mdi is not None and len(mdi) == 0
            assert mdt is not None and len(mdt) == 0
        except Exception as e:
            print(e)

    finally:
        # Clean up
        # if channel is not None:
        #     await channel.close()
        await srv.stop(0)


@pytest.mark.asyncio
async def test_custom_resolver() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._interceptor import InterceptedUnaryUnaryCall as UnaryUnaryCall
    from grpc.aio._metadata import Metadata

    import nebius.api.nebius.compute.v1.disk_pb2 as disk_pb2
    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1.disk_service_pb2 import (
        GetDiskRequest,
    )
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import (
        DiskServiceServicer,
        DiskServiceStub,
        add_DiskServiceServicer_to_server,
    )
    from nebius.base.options import INSECURE
    from nebius.base.resolver import Single

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
            credentials=NoCredentials(),
            resolver=Single("nebius.compute.v1.DiskService", address),
            options=[(INSECURE, True)],
        )
        stub = DiskServiceStub(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = stub.Get(req)
        assert isinstance(call, UnaryUnaryCall)

        # Await response and metadata
        ret = await call
        assert isinstance(ret, disk_pb2.Disk)
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        code = await call.code()
        details = await call.details()

        # Assertions to validate behavior
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"
        assert code == grpc.StatusCode.OK
        assert details == ""
        assert mdi is not None and len(mdi) == 0
        assert mdt is not None and len(mdt) == 0

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)
