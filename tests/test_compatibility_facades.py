from __future__ import annotations

import importlib
from typing import Any


def test_message_only_grpc_compatibility_module_is_importable() -> None:
    module = importlib.import_module("nebius.api.nebius.compute.v1.disk_pb2_grpc")
    assert module.__doc__


def test_service_only_pb2_facade_keeps_file_descriptor() -> None:
    from nebius.api.nebius.iam.v1 import token_exchange_service_pb2

    assert token_exchange_service_pb2.DESCRIPTOR.name.endswith(
        "token_exchange_service.proto"
    )


def test_experimental_service_static_rpc_api(monkeypatch: Any) -> None:
    import grpc.experimental

    from nebius.api.nebius.compute.v1 import GetDiskRequest
    from nebius.api.nebius.compute.v1.disk_service_pb2_grpc import DiskService

    recorded: list[tuple[Any, ...]] = []
    sentinel = object()

    def unary_unary(*args: Any) -> object:
        recorded.append(args)
        return sentinel

    monkeypatch.setattr(grpc.experimental, "unary_unary", unary_unary)
    request = GetDiskRequest(id="disk-id")

    assert DiskService.Get(request, "compute.example", timeout=3.0) is sentinel
    assert recorded[0][0] is request
    assert recorded[0][1:3] == (
        "compute.example",
        "/nebius.compute.v1.DiskService/Get",
    )
    assert recorded[0][11] == 3.0


def test_stub_endpoint_annotation_is_available_before_client_creation() -> None:
    from nebius.aio.service_descriptor import from_stub_class
    from nebius.api.nebius.kms.v1.symmetric_key_service_pb2_grpc import (
        SymmetricKeyServiceStub,
    )
    from nebius.base.resolver import Conventional

    service = from_stub_class(SymmetricKeyServiceStub)

    assert service == "nebius.kms.v1.SymmetricKeyService"
    assert Conventional().resolve(service) == "cpl.kms.{domain}"
