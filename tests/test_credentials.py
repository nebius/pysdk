# type: ignore
import logging

import pytest


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
