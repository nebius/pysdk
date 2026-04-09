# type: ignore
from __future__ import annotations

from datetime import datetime, timezone


def test_unset_metadata_timestamp_returns_none() -> None:
    from google.protobuf.timestamp_pb2 import Timestamp

    from nebius.api.nebius.common.v1 import ResourceMetadata, metadata_pb2
    from nebius.api.nebius.iam.v1 import (
        ListTenantUserAccountsWithAttributesResponse,
        TenantUserAccount,
        TenantUserAccountWithAttributes,
    )
    from nebius.base.protos.well_known import local_timezone

    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    created_at_pb = Timestamp()
    created_at_pb.FromDatetime(created_at)

    metadata_pb = metadata_pb2.ResourceMetadata()
    metadata_pb.created_at.CopyFrom(created_at_pb)
    assert metadata_pb.HasField("created_at")
    assert not metadata_pb.HasField("updated_at")

    response = ListTenantUserAccountsWithAttributesResponse(
        items=[
            TenantUserAccountWithAttributes(
                tenant_user_account=TenantUserAccount(
                    metadata=ResourceMetadata(metadata_pb),
                ),
            )
        ]
    )

    metadata = response.items[0].tenant_user_account.metadata
    assert metadata.created_at == created_at.astimezone(local_timezone)
    assert metadata.updated_at is None
