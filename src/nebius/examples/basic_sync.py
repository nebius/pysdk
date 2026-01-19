import argparse
import os
from time import time  # type: ignore[unused-ignore]

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
from nebius.sdk import SDK

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG)

    def sync_main() -> None:
        parser = argparse.ArgumentParser(
            "examples/basic_sync.py",
            description="basic example that creates and then deletes a bucket",
        )
        parser.add_argument(
            "project_id", help="project in which to create and delete a test bucket."
        )
        args = parser.parse_args()

        sdk = SDK(
            credentials=Bearer(
                Token(
                    os.environ.get("NEBIUS_IAM_TOKEN", ""),
                )
            ),
        )
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
            status = req.current_status()
            print(status)
            ret = req.wait()
            mdi = req.initial_metadata_sync()
            mdt = req.trailing_metadata_sync()
            status = req.current_status()
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
        sdk.sync_close()

    sync_main()
