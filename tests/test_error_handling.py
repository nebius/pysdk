# type: ignore
import logging

import pytest


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
