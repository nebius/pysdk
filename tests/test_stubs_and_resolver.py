# type: ignore
import logging

import pytest
from grpc_service import add_service

from nebius.aio import request

request.DEFAULT_AUTH_TIMEOUT = 5.0


@pytest.mark.asyncio
async def test_get_instance() -> None:
    import grpc
    import grpc.aio

    # Imports needed inside the test function
    from grpc.aio._metadata import Metadata

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1 import (
        Disk,
        DiskServiceClient,
        GetDiskRequest,
    )
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService:
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, Disk],
        ) -> Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            # Return an Instance object as expected by the client
            ret = Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
            return ret

    # Randomly assign an IPv6 address and port for the server
    srv = grpc.aio.server()
    assert isinstance(srv, grpc.aio.Server)
    port = srv.add_insecure_port("[::]:0")
    add_service(srv, DiskServiceClient, MockInstanceService())
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address, options=[(INSECURE, True)], credentials=NoCredentials()
        )
        client = DiskServiceClient(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = client.get(req)

        # Await response and metadata
        ret = await call
        assert isinstance(ret, Disk)
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        status = await call.status()

        # Assertions to validate behavior
        assert ret.HasField("metadata")
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"
        assert status.code == grpc.StatusCode.OK
        assert status.message == ""
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
    from grpc.aio._metadata import Metadata

    from nebius.aio.channel import Channel
    from nebius.aio.token.static import Bearer
    from nebius.api.nebius.compute.v1 import (
        Disk,
        DiskServiceClient,
        GetDiskRequest,
    )
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService:
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, Disk],
        ) -> Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            # Return an Instance object as expected by the client
            ret = Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
            return ret

    # Randomly assign an IPv6 address and port for the server
    srv = grpc.aio.server()
    assert isinstance(srv, grpc.aio.Server)
    port = srv.add_insecure_port("[::]:0")
    add_service(srv, DiskServiceClient, MockInstanceService())
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address, options=[(INSECURE, True)], credentials=Bearer("abc")
        )
        client = DiskServiceClient(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = client.get(req, timeout=1)

        # Await response and metadata
        ret = await call
        assert isinstance(ret, Disk)
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        status = await call.status()

        # Assertions to validate behavior
        assert ret.HasField("metadata")
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"
        assert status.code == grpc.StatusCode.OK
        assert status.message == ""
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
    from grpc.aio._metadata import Metadata

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.common.v1 import QuotaFailure, ServiceError
    from nebius.api.nebius.compute.v1 import (
        Disk,
        DiskServiceClient,
        GetDiskRequest,
    )
    from nebius.base._service_error import trailing_metadata_of_errors
    from nebius.base.options import INSECURE

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService:
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, Disk],
        ) -> Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            quota_violation = QuotaFailure.Violation(
                quota="test_quota",
                message="testing quota failure",
                limit="42",
                requested="69",
            )
            quota_failure = QuotaFailure(violations=[quota_violation])
            service_error = ServiceError(
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
    add_service(srv, DiskServiceClient, MockInstanceService())
    await srv.start()

    # Use the actual port assigned by the server
    address = f"localhost:{port}"

    channel = None
    try:
        # Set up the client channel
        channel = Channel(
            domain=address, options=[(INSECURE, True)], credentials=NoCredentials()
        )
        client = DiskServiceClient(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = client.get(req)

        # Await response and metadata
        try:
            mdi = await call.initial_metadata()
            mdt = await call.trailing_metadata()
            status = await call.status()
            ret = await call
            assert isinstance(ret, Disk)

            # Assertions to validate behavior
            assert ret.metadata.id == "foo-bar"
            assert ret.metadata.name == "MockDisk"
            assert status.code == grpc.StatusCode.OK
            assert status.message == ""
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
    from grpc.aio._metadata import Metadata

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.api.nebius.compute.v1 import (
        Disk,
        DiskServiceClient,
        GetDiskRequest,
    )
    from nebius.base.options import INSECURE
    from nebius.base.resolver import Single

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Define a mock server class
    class MockInstanceService:
        async def Get(  # noqa: N802 — GRPC method
            self,
            request: GetDiskRequest,
            context: grpc.aio.ServicerContext[GetDiskRequest, Disk],
        ) -> Disk:
            assert request.id == "foo-bar"
            md = context.invocation_metadata()
            assert md is not None
            # Recreate metadata for ease of checking
            md = Metadata(*[v for v in md])
            assert md.get("x-idempotency-key", "") != ""

            # Return an Instance object as expected by the client
            ret = Disk()
            ret.metadata.id = request.id
            ret.metadata.name = "MockDisk"
            return ret

    # Randomly assign an IPv6 address and port for the server
    srv = grpc.aio.server()
    assert isinstance(srv, grpc.aio.Server)
    port = srv.add_insecure_port("[::]:0")
    add_service(srv, DiskServiceClient, MockInstanceService())
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
        client = DiskServiceClient(channel)

        # Make a request
        req = GetDiskRequest(id="foo-bar")
        call = client.get(req)

        # Await response and metadata
        ret = await call
        assert isinstance(ret, Disk)
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        status = await call.status()

        # Assertions to validate behavior
        assert ret.metadata.id == "foo-bar"
        assert ret.metadata.name == "MockDisk"
        assert status.code == grpc.StatusCode.OK
        assert status.message == ""
        assert mdi is not None and len(mdi) == 0
        assert mdt is not None and len(mdt) == 0

    finally:
        # Clean up
        if channel is not None:
            await channel.close()
        await srv.stop(0)
