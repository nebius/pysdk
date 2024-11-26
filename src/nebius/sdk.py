import os
from asyncio import sleep
from time import time

from grpc.aio._call import UnaryUnaryCall

from nebius.aio.channel import Channel
from nebius.aio.token.static import Bearer
from nebius.aio.token.token import Token
from nebius.api.nebius.common.v1.metadata_pb2 import ResourceMetadata
from nebius.api.nebius.common.v1.operation_pb2 import Operation
from nebius.api.nebius.common.v1.operation_service_pb2 import GetOperationRequest
from nebius.api.nebius.storage.v1.base_pb2 import VersioningPolicy
from nebius.api.nebius.storage.v1.bucket_pb2 import Bucket, BucketSpec
from nebius.api.nebius.storage.v1.bucket_service_pb2 import (
    CreateBucketRequest,
    DeleteBucketRequest,
    GetBucketRequest,
)
from nebius.api.nebius.storage.v1.bucket_service_pb2_grpc import BucketServiceStub

SERVER = "[::1]:50051"


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    async def main() -> None:
        channel = Channel(
            domain="api.private-api.tst.man.nbhost.net:443",
            credentials=Bearer(
                Token(
                    os.environ.get("NEBIUS_IAM_TOKEN", ""),
                )
            ),
        )

        stub = BucketServiceStub(channel)  # type: ignore
        op_service = channel.get_corresponding_operation_service(BucketServiceStub)
        req = CreateBucketRequest(
            metadata=ResourceMetadata(
                parent_id=os.environ.get("PROJECT_ID", ""),
                name=f"test-pysdk-bucket-{time()}",
            ),
            spec=BucketSpec(
                versioning_policy=VersioningPolicy.DISABLED,
                max_size_bytes=4096,
            ),
        )
        call: UnaryUnaryCall = stub.Create(req)
        ret: Operation = await call
        mdi = await call.initial_metadata()
        mdt = await call.trailing_metadata()
        code = await call.code()
        details = await call.details()
        print(ret)
        print(mdi, mdt, code, details)
        while not ret.HasField("status"):
            print("waiting 1 sec for operation to complete...")
            await sleep(1)
            ret = await op_service.Get(GetOperationRequest(id=ret.id))
            print(ret)
        bucket: Bucket = await stub.Get(GetBucketRequest(id=ret.resource_id))
        print(bucket)
        await stub.Delete(DeleteBucketRequest(id=bucket.metadata.id))

    import asyncio

    asyncio.run(main())
