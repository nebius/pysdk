"""Test idempotency keys with SDK and native gRPC metadata."""

from uuid import UUID

import pytest
from grpc.aio import Metadata as GRPCMetadata
from nebius.aio.idempotency import HEADER, ensure_key_in_metadata
from nebius.base.metadata import Metadata


@pytest.mark.parametrize("metadata_type", [Metadata, GRPCMetadata])
@pytest.mark.parametrize("values", [[], [""], ["existing"], ["first", "second"]])
def test_ensure_idempotency_key(metadata_type: type[Metadata] | type[GRPCMetadata], values: list[str]) -> None:
    entries = [(HEADER, value) for value in values]
    metadata = Metadata(entries) if metadata_type is Metadata else GRPCMetadata(*entries)

    ensure_key_in_metadata(metadata)
    result = [value for key, value in metadata if key == HEADER]
    if values and values != [""]:
        assert result == values
    else:
        assert len(result) == 1
        assert UUID(result[0]).version == 4

    ensure_key_in_metadata(metadata)
    assert [value for key, value in metadata if key == HEADER] == result
