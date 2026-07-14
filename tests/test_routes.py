from __future__ import annotations

from nebius.aio.channel import Channel
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
