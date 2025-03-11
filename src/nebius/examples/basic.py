import argparse
from time import time  # type: ignore[unused-ignore]

from nebius.aio.service_error import RequestError
from nebius.api.nebius.common.v1 import ResourceMetadata
from nebius.api.nebius.storage.v1 import (
    BucketServiceClient,
    BucketSpec,
    CreateBucketRequest,
    DeleteBucketRequest,
    GetBucketRequest,
    VersioningPolicy,
)
from nebius.sdk import SDK

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    async def main() -> None:
        parser = argparse.ArgumentParser(
            "examples/basic.py",
            description="basic example that creates and then deletes a bucket",
        )
        parser.add_argument("--domain", help="domain override", default=None)
        parser.add_argument(
            "project_id", help="project in which to create and delete a test bucket"
        )
        args = parser.parse_args()

        sdk = SDK(domain=args.domain)
        print(await sdk.whoami())

        project_id: str = args.project_id

        service = BucketServiceClient(sdk)
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

    import asyncio

    asyncio.run(main())
