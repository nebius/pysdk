"""Helpers for injecting protobuf-derived reset masks into metadata."""

from collections.abc import Iterable
from typing import Protocol

from nebius.base.fieldmask import Mask
from nebius.base.metadata import Metadata

RESET_MASK_HEADER = "X-ResetMask"
"""Metadata header name used for reset masks."""


class ResetMaskMessage(Protocol):
    def get_full_update_reset_mask(self) -> Mask: ...


def ensure_reset_mask_in_metadata(
    msg: ResetMaskMessage,
    metadata: Iterable[tuple[str, str]] | None,
) -> Metadata:
    """Ensure the reset mask header is present in request metadata.

    This helper builds a :class:`nebius.base.metadata.Metadata` instance from
    the provided iterable and populates the ``X-ResetMask`` header when it is
    missing. The mask is derived from the protobuf message by calling
    the message's ``get_full_update_reset_mask`` method.

    Example
    -------

    Use the helper before sending an update request::

        from nebius.base.fieldmask_protobuf import ensure_reset_mask_in_metadata

        md = ensure_reset_mask_in_metadata(request, metadata=None)
        await service.update(request, metadata=md)

    :param msg: Protobuf message used to derive the full update reset mask.
    :param metadata: Existing metadata entries or ``None``.
    :returns: A :class:`Metadata` instance containing the reset mask header.
    """
    metadata = Metadata(metadata)

    if RESET_MASK_HEADER not in metadata:  # type: ignore[comparison-overlap]
        metadata[RESET_MASK_HEADER] = msg.get_full_update_reset_mask().marshal()
    return metadata
