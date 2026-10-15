"""Check terminal operation errors in both public operation versions."""

from asyncio import run

import pytest
from grpc import StatusCode
from nebius.aio.channel import Channel, NoCredentials
from nebius.aio.operation import Operation, OperationError
from nebius.aio.service_error import RequestError
from nebius.api.google.rpc import Status
from nebius.api.nebius.common.v1 import Operation as OperationV1
from nebius.api.nebius.common.v1 import ServiceError
from nebius.api.nebius.common.v1alpha1 import Operation as OperationAlpha


@pytest.mark.parametrize("message_type", [OperationV1, OperationAlpha])
@pytest.mark.parametrize("synchronous", [False, True])
@pytest.mark.parametrize("already_done", [False, True])
def test_wait_reports_failed_operation(message_type, synchronous, already_done) -> None:
    """Report the final status whether failure precedes or follows polling."""
    channel = Channel(user_agent_prefix="sdk-parity-tests/1.0", credentials=NoCredentials())
    service_error = ServiceError(service="example", code="ExampleFailure")
    terminal = message_type(
        id="operation-failed",
        status=Status(
            code=StatusCode.INTERNAL.value[0],
            message="failed",
            details=[Status.__REGISTRY__.pack_any(service_error)],
        ),
    )
    operation = Operation(
        ".nebius.common.v1.OperationService.Get",
        channel,
        terminal if already_done else message_type(id="operation-failed"),
    )

    class Service:
        def get(self, request, **kwargs):
            async def result():
                class Response:
                    _operation = terminal

                return Response()

            return result()

    operation._service = Service()
    try:
        with pytest.raises(OperationError) as raised:
            if synchronous:
                operation.sync_wait(timeout=2)
            else:
                run(operation.wait(timeout=2))
        error = raised.value
        assert isinstance(error, RequestError)
        assert error.operation is operation
        assert error.code == StatusCode.INTERNAL
        assert error.message == "failed"
        assert len(error.status.service_errors) == 1
        assert error.status.service_errors[0].code == service_error.code
    finally:
        channel.sync_close()
