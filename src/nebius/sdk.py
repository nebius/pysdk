import os
from time import time

from nebius.aio.channel import Channel
from nebius.aio.service_error import RequestError
from nebius.aio.token.static import Bearer
from nebius.aio.token.token import Token
from nebius.api.nebius.common.v1 import ResourceMetadata
from nebius.api.nebius.storage.v1 import (
    BucketServiceClient,
    BucketSpec,
    CreateBucketRequest,
    DeleteBucketRequest,
    GetBucketRequest,
    VersioningPolicy,
)

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    def sync_main() -> None:
        channel = Channel(
            credentials=Bearer(
                Token(
                    os.environ.get("NEBIUS_IAM_TOKEN", ""),
                )
            ),
        )
        project_id = os.environ.get("PROJECT_ID", "")

        service = BucketServiceClient(channel)
        try:
            req = service.create(
                CreateBucketRequest(
                    metadata=ResourceMetadata(
                        parent_id=project_id,
                        name=f"test-pysdk-bucket-{time()}",
                    ),
                    spec=BucketSpec(
                        versioning_policy=VersioningPolicy.DISABLED,
                        max_size_bytes=4096,
                    ),
                )
            )
            ret = req.wait()
            mdi = req.initial_metadata_sync()
            mdt = req.trailing_metadata_sync()
            status = req.status_sync()
            # or just do `ret: Operation = await service.Create(req)`
            print(ret)
            print(mdi, mdt, status)
            ret.sync_wait()
            print(ret)
            bucket = service.get(GetBucketRequest(id=ret.resource_id)).wait()
            print(bucket)
            service.delete(DeleteBucketRequest(id=bucket.metadata.id)).wait()
        except RequestError as e:
            print(e)
            raise
        channel.sync_close()

    async def main() -> None:
        channel = Channel(
            credentials=Bearer(
                Token(
                    os.environ.get("NEBIUS_IAM_TOKEN", ""),
                )
            ),
        )
        project_id = os.environ.get("PROJECT_ID", "")

        service = BucketServiceClient(channel)
        try:
            req = service.create(
                CreateBucketRequest(
                    metadata=ResourceMetadata(
                        parent_id=project_id,
                        name=f"test-pysdk-bucket-{time()}",
                    ),
                    spec=BucketSpec(
                        versioning_policy=VersioningPolicy.DISABLED,
                        max_size_bytes=4096,
                    ),
                )
            )
            ret = await req
            mdi = await req.initial_metadata()
            mdt = await req.trailing_metadata()
            status = await req.status()
            # or just do `ret: Operation = await service.Create(req)`
            print(ret)
            print(mdi, mdt, status)
            await ret.wait()
            print(ret)
            bucket = await service.get(GetBucketRequest(id=ret.resource_id))
            print(bucket)
            await service.delete(DeleteBucketRequest(id=bucket.metadata.id))
        except RequestError as e:
            print(e)
            raise

    sync_main()
    # import asyncio
    # asyncio.run(main())
