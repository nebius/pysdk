# type: ignore
import logging

import pytest

from nebius.aio import request

request.DEFAULT_AUTH_TIMEOUT = 5.0


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


def _status_with_message(message: str, code=None):
    from grpc import StatusCode

    from nebius.aio.service_error import RequestStatusExtended

    return RequestStatusExtended(
        code=code or StatusCode.UNKNOWN,
        message=message,
        details=[],
        service_errors=[],
        request_id="",
        trace_id="",
    )


@pytest.mark.parametrize(
    "message",
    [
        "Received http2 header with status: 520",
        "Received HTTP2 header with status: 524",
        "unexpected HTTP status code received from server: 522",
        (
            "Error received from peer "
            '{grpc_message:"Received http2 header with status: 523"}'
        ),
        "proxy failed with HTTP status code 529",
    ],
)
def test_unknown_http_52x_status_is_retriable_after_sdk_wrapping(
    message: str,
) -> None:
    from nebius.aio.service_error import RequestError, is_retriable_error

    status = _status_with_message(message)

    assert status.is_retriable()
    assert is_retriable_error(RequestError(status))


@pytest.mark.parametrize(
    ("message", "code_name"),
    [
        ("Received http2 header with status: 404", "UNKNOWN"),
        ("Received http2 header with status: 500", "UNKNOWN"),
        ("unexpected HTTP status code received from server: 502", "UNKNOWN"),
        (
            "Error received from peer "
            '{grpc_message:"Received http2 header with status: 503"}',
            "UNKNOWN",
        ),
        ("Received http2 header with status: 519", "UNKNOWN"),
        ("Received http2 header with status: 530", "UNKNOWN"),
        ("proxy failed with HTTP status code 599", "UNKNOWN"),
        ("unknown service error 503", "UNKNOWN"),
        ("unknown service error 523", "UNKNOWN"),
        ("Received http2 header with status: 502", "INTERNAL"),
    ],
)
def test_non_52x_unknown_http_status_is_not_retriable(
    message: str,
    code_name: str,
) -> None:
    from grpc import StatusCode

    code = getattr(StatusCode, code_name)
    assert not _status_with_message(message, code).is_retriable()


def test_raw_grpc_unknown_http_52x_status_is_retriable() -> None:
    from grpc import StatusCode
    from grpc.aio import AioRpcError
    from grpc.aio._metadata import Metadata

    from nebius.aio.service_error import is_retriable_error

    err = AioRpcError(
        StatusCode.UNKNOWN,
        Metadata(),
        Metadata(),
        "Received http2 header with status: 522",
        (
            "Error received from peer "
            '{grpc_message:"Received http2 header with status: 522"}'
        ),
    )

    assert is_retriable_error(err)


def test_chained_request_error_http_52x_status_is_retriable() -> None:
    from nebius.aio.service_error import RequestError, is_retriable_error

    inner = RequestError(_status_with_message("Received http2 header with status: 523"))
    outer = RuntimeError("request failed")
    outer.__cause__ = inner

    assert is_retriable_error(outer)


def _h2_frame(frame_type, flags, stream_id, payload=b""):
    return (
        len(payload).to_bytes(3, "big")
        + bytes([frame_type, flags])
        + (stream_id & 0x7FFFFFFF).to_bytes(4, "big")
        + payload
    )


async def _read_h2_frame(reader):
    header = await reader.readexactly(9)
    length = int.from_bytes(header[:3], "big")
    frame_type = header[3]
    flags = header[4]
    stream_id = int.from_bytes(header[5:], "big") & 0x7FFFFFFF
    payload = await reader.readexactly(length)
    return frame_type, flags, stream_id, payload


@pytest.mark.asyncio
async def test_http2_52x_status_from_server_is_retried() -> None:
    import asyncio

    from nebius.aio.channel import Channel, NoCredentials
    from nebius.aio.service_error import RequestError
    from nebius.api.nebius.compute.v1 import DiskServiceClient, GetDiskRequest
    from nebius.base.options import INSECURE
    from nebius.base.resolver import Constant

    preface = b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n"
    attempts = 0

    async def handle(reader, writer):
        nonlocal attempts
        try:
            await reader.readexactly(len(preface))
            writer.write(_h2_frame(4, 0, 0))
            await writer.drain()

            while attempts < 2:
                stream_id = None
                while stream_id is None:
                    frame_type, flags, read_stream_id, _ = await _read_h2_frame(reader)
                    if frame_type == 4 and not flags & 0x1:
                        writer.write(_h2_frame(4, 0x1, 0))
                        await writer.drain()
                    elif frame_type == 1:
                        stream_id = read_stream_id

                attempts += 1
                # HPACK literal header field without indexing, indexed name 8 (:status).
                header_block = b"\x08\x03" + b"522"
                writer.write(_h2_frame(1, 0x5, stream_id, header_block))
                await writer.drain()

            await asyncio.sleep(0.01)
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    socket = server.sockets[0]
    address = f"127.0.0.1:{socket.getsockname()[1]}"
    channel = Channel(
        resolver=Constant(address),
        options=[(INSECURE, True)],
        credentials=NoCredentials(),
    )

    try:
        client = DiskServiceClient(channel)
        req = client.get(
            GetDiskRequest(id="foo-bar"),
            retries=2,
            timeout=5,
            per_retry_timeout=1,
        )

        with pytest.raises(RequestError) as exc_info:
            await req

        assert attempts == 2
        assert exc_info.value.status.code.name == "UNKNOWN"
        assert "522" in (exc_info.value.status.message or "")
    finally:
        await channel.close()
        server.close()
        await server.wait_closed()


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
