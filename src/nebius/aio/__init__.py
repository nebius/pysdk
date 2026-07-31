"""Asynchronous Nebius SDK package.

The package exports :class:`CrossLoopAwaitable` for annotations on handles
returned by SDK asynchronous submission and background-work methods.
"""

from ._runtime import CrossLoopAwaitable

__all__ = ["CrossLoopAwaitable"]
