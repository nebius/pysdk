from grpc.aio._call import UnaryUnaryCall

from nebius.aio.channel import Channel
from nebius.api.nebius.compute.v1.disk_service_pb2 import (
    ListDisksRequest,
)
from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import DiskServiceStub
from nebius.base.service_account.credentials_file import Reader as SACReader

SERVER = "[::1]:50051"


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    async def main() -> None:
        channel = Channel(
            domain="api.private-api.tst.man.nbhost.net:443",
            credentials=SACReader(
                "/home/complynx/nebo/api/tools/terraform/test/e2e/credentials/npc_e2e_credentials.json"
            ),
        )

        stub = DiskServiceStub(channel)  # type: ignore
        # op_service = channel.get_corresponding_operation_service(DiskServiceStub)
        req = ListDisksRequest(parent_id="project-e0tpublic-api-gateway")
        call: UnaryUnaryCall = stub.List(req)
        ret = await call
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        code = await call.code()
        details = await call.details()
        print(ret)
        print(mdi, mdt, code, details)

    import asyncio

    asyncio.run(main())
