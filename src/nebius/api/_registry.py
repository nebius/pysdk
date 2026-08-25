"""Registry for SDK types generated inside the Nebo monorepo."""

from ..base.protos.dynamic import EXTENSION_HANDLES
from ..base.protos.dynamic import EXTENSIONS
from ..base.protos.dynamic import REGISTRY

REGISTRY.load_all()

__all__ = ["EXTENSIONS", "EXTENSION_HANDLES", "REGISTRY"]
