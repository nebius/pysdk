from grpc.aio._call import UnaryUnaryCall

from nebius.aio.channel import Channel
from nebius.aio.token import static
from nebius.aio.token.token import Token
from nebius.api.nebius.compute.v1.disk_service_pb2 import (
    ListDisksRequest,
)
from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import DiskServiceStub

SERVER = "[::1]:50051"


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    async def main() -> None:
        channel = Channel(
            domain="api.private-api.tst.man.nbhost.net:443",
            credentials=static.Bearer(
                Token(
                    "ne1CtIBCh5hY2Nlc3N0b2tlbi1lMHRuOXY2eHoxeGVzYzN3a2YSIXVzZXJhY2NvdW50LWUwdG"
                    "JqbnFjZ3ZuYnJwcHplcXFzbhpfChpzZXNzaW9uLWUwdHdjdjR5MDN4OTJkYmIyYRAEGj8KGXN"
                    "lcnZpY2VhY2NvdW50LWUwdGlhbS1jcGwQAxogChxwdWJsaWNrZXktZTB0djNkOXlkYXQxaGFn"
                    "N3JjEAEqC25wY19zZXNzaW9uMgwIpe3YuQYQl9balwI6DAjlvtu5BhCX1tqXAloDZTB0.AAAA"
                    "AAAAAAEAAAAAAABOSQAAAAAAAAAD4020JGwdo_i3JPNDTpsgj4_BwjGBfOPUa7j502JwJPi3A"
                    "4zD6l6dwaFGHu3-A_ZX_ok6Ps4Mqlz6JgKUxF3iDA"
                )
            ),
        )

        stub = DiskServiceStub(channel)  # type: ignore
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
