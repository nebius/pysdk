from __future__ import annotations

import asyncio

from nebius.aio.channel import Channel, NoCredentials
from nebius.aio.route import Route
from nebius.base.resolver import Prefix, TemplateExpander


def _bare_channel() -> Channel:
    channel = Channel.__new__(Channel)
    channel._route_substitutions = {"{domain}": "api.example"}
    channel._route_custom_resolver = None
    channel._routes = {}
    return channel


def test_generated_endpoint_route_does_not_need_global_descriptor_pool() -> None:
    channel = _bare_channel()
    route = Route(
        service="nebius.iam.v1.TokenService",
        method="Create",
        api_service_name="cpl.iam",
        registry=object(),
    )

    assert channel.get_addr_by_route(route) == "cpl.iam.api.example"


def test_explicit_resolver_precedes_generated_endpoint() -> None:
    channel = _bare_channel()
    channel._route_custom_resolver = TemplateExpander(
        channel._route_substitutions,
        Prefix("nebius.iam.", "localhost:1234"),
    )
    route = Route(
        service="nebius.iam.v1.TokenService",
        method="Create",
        api_service_name="cpl.iam",
    )

    assert channel.get_addr_by_route(route) == "localhost:1234"


def test_method_and_route_fallbacks_keep_public_resolver_override() -> None:
    """Internal dispatch must preserve the established subclass hook."""

    resolver_loops: list[asyncio.AbstractEventLoop] = []

    class CustomChannel(Channel):
        def get_addr_from_service_name(self, service_name: str) -> str:
            resolver_loops.append(asyncio.get_running_loop())
            return f"{service_name}.custom:443"

    channel = CustomChannel(credentials=NoCredentials())
    route = Route(service="acme.RouteService", method="Get")
    try:
        assert channel.get_addr_by_method("/acme.MethodService/Get") == "acme.MethodService.custom:443"
        assert channel.get_addr_by_route(route) == "acme.RouteService.custom:443"
        assert resolver_loops == [channel._event_loop, channel._event_loop]
    finally:
        channel.sync_close(timeout=5)
