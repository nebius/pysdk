"""
End-to-end test for storage bucket operations using Nebius SDK.

This test requires NEBIUS_E2E_CONFIG_FILE environment variable to be set
to a valid YAML config file. If the environment variable is not set or
the file is invalid, the test will be skipped.
"""

import base64
import binascii
import os
import random
import string
import tempfile
from pathlib import Path

import pytest
import yaml

from nebius.aio.cli_config import Config
from nebius.api.nebius.common.v1 import ResourceMetadata
from nebius.api.nebius.storage.v1 import (
    BucketServiceClient,
    BucketSpec,
    CreateBucketRequest,
    DeleteBucketRequest,
    GetBucketRequest,
    ListBucketsRequest,
    VersioningPolicy,
)
from nebius.sdk import SDK


def _generate_random_string(length: int = 8) -> str:
    """Generate a random string of lowercase letters and digits."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _get_config_file_path() -> tuple[str | None, bool]:
    """
    Get the config file path from environment variable.

    Returns:
        tuple: (config_file_path, is_temp_file)
        - config_file_path: Path to the config file or None if not available
        - is_temp_file: True if the file was created from base64 content
    """
    # First try NEBIUS_E2E_CONFIG_FILE
    config_file = os.environ.get("NEBIUS_E2E_CONFIG_FILE")
    if config_file and Path(config_file).exists():
        return config_file, False

    # If file env var not found or file doesn't exist, try base64 variant
    config_b64 = os.environ.get("NEBIUS_E2E_CONFIG_B64")
    if not config_b64:
        return None, False

    try:
        # Decode base64 content
        config_content = base64.b64decode(config_b64).decode("utf-8")

        # Validate that it's valid YAML
        yaml.safe_load(config_content)

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", prefix="nebius_e2e_config_", delete=False
        )
        temp_file.write(config_content)
        temp_file.close()

        return temp_file.name, True

    except (binascii.Error, UnicodeDecodeError, yaml.YAMLError, OSError):
        return None, False


def _validate_yaml_config(config_file: str) -> bool:
    """Validate that the config file is a valid YAML."""
    try:
        with open(config_file, "r") as f:
            yaml.safe_load(f)
        return True
    except (yaml.YAMLError, OSError):
        return False


@pytest.mark.asyncio
async def test_e2e_storage_bucket_lifecycle() -> None:
    """
    End-to-end test for storage bucket lifecycle:
    1. Create a storage bucket with specific configuration
    2. Get the bucket by ID
    3. List buckets and verify our bucket is present
    4. Delete the bucket
    """
    # Check if config file is set and valid
    config_file, is_temp_file = _get_config_file_path()
    try:
        if not config_file:
            pytest.skip(
                "Neither NEBIUS_E2E_CONFIG_FILE nor NEBIUS_E2E_CONFIG_B64 "
                "environment variable is set or valid"
            )

        if not is_temp_file and not _validate_yaml_config(config_file):
            pytest.skip("NEBIUS_E2E_CONFIG_FILE does not point to a valid YAML file")

        # Create SDK from config
        config = Config(config_file=config_file)
        sdk = SDK(config_reader=config)

        # Get parent ID for assertions
        parent_id = config.parent_id
        assert parent_id is not None, "Parent ID should not be None"
        assert parent_id == sdk.parent_id(), "Parent ID should match SDK's parent ID"

        # Generate unique bucket name
        random_suffix = _generate_random_string()
        bucket_name = f"python-e2e-{random_suffix}"

        bucket_service = BucketServiceClient(sdk)
        bucket_id = None

        async with sdk:
            try:
                # Create bucket
                create_request = CreateBucketRequest(
                    metadata=ResourceMetadata(
                        name=bucket_name,
                    ),
                    spec=BucketSpec(
                        versioning_policy=VersioningPolicy.DISABLED,
                        max_size_bytes=4096,
                    ),
                )

                create_operation = await bucket_service.create(create_request)
                await create_operation.wait()
                bucket_id = create_operation.resource_id

                assert (
                    bucket_id is not None
                ), "Bucket creation should return a valid bucket ID"

                # Get bucket by ID
                get_request = GetBucketRequest(id=bucket_id)
                bucket = await bucket_service.get(get_request)

                assert bucket.metadata.id == bucket_id
                assert bucket.metadata.name == bucket_name
                assert bucket.spec.versioning_policy == VersioningPolicy.DISABLED
                assert bucket.spec.max_size_bytes == 4096

                # List buckets and find our bucket
                list_request = ListBucketsRequest(parent_id=parent_id)
                buckets_response = await bucket_service.list(list_request)

                # Find our bucket in the list
                found_bucket = None
                for bucket_item in buckets_response.items:
                    if bucket_item.metadata.id == bucket_id:
                        found_bucket = bucket_item
                        break

                assert (
                    found_bucket is not None
                ), f"Bucket {bucket_id} should be found in the list"
                assert found_bucket.metadata.name == bucket_name

                delete_request = DeleteBucketRequest(id=bucket_id)
                delete_operation = await bucket_service.delete(delete_request)
                await delete_operation.wait()
                bucket_id = None  # Reset bucket_id after deletion

            except Exception as e:
                # If test fails, still try to cleanup
                if bucket_id:
                    try:
                        delete_request = DeleteBucketRequest(id=bucket_id)
                        delete_operation = await bucket_service.delete(delete_request)
                        await delete_operation.wait()
                    except Exception as cleanup_error:
                        # Log cleanup error but don't fail the test
                        print(
                            "Warning: Failed to cleanup bucket "
                            f"{bucket_id}: {cleanup_error}"
                        )
                raise e

    finally:
        # Cleanup temporary config file if created from base64
        if is_temp_file and config_file and Path(config_file).exists():
            try:
                os.unlink(config_file)
            except OSError:
                pass  # Ignore cleanup errors for temp file


if __name__ == "__main__":
    # Allow running the test directly for debugging
    import asyncio

    async def main() -> None:
        await test_e2e_storage_bucket_lifecycle()

    asyncio.run(main())
