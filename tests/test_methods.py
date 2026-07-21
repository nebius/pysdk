"""Tests for parsing fully-qualified RPC method identifiers."""

import pytest

from nebius.base.methods import InvalidMethodNameError, service_from_method_name


@pytest.mark.parametrize(
    "method",
    (
        "nebius.storage.v1.BucketService.Create",
        "nebius.storage.v1.BucketService/Create",
        "/nebius.storage.v1.BucketService/Create",
        ".nebius.storage.v1.BucketService.Create",
    ),
)
def test_service_from_method_name_keeps_complete_service(method: str) -> None:
    assert service_from_method_name(method) == "nebius.storage.v1.BucketService"


@pytest.mark.parametrize(
    "method",
    (
        "/nebius.storage.v1.BucketService.Create",
        ".nebius.storage.v1.BucketService/Create",
        "nebius.storage.v1.BucketService.",
        "/nebius.storage.v1.BucketService/Create/extra",
    ),
)
def test_service_from_method_name_rejects_malformed_names(method: str) -> None:
    with pytest.raises(InvalidMethodNameError):
        service_from_method_name(method)
