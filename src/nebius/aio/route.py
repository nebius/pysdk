"""Immutable namespace-aware route metadata emitted by service clients."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    service: str
    method: str
    api_service_name: str = ""
    registry: object | None = None

    @property
    def method_name(self) -> str:
        return f"{self.service}.{self.method}"
