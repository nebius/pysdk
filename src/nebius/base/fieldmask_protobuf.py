from collections.abc import Iterable

from nebius.base.metadata import Metadata
from nebius.base.protos.pb_classes import Message

RESET_MASK_HEADER = "X-ResetMask"


def ensure_reset_mask_in_metadata(
    msg: Message,
    metadata: Iterable[tuple[str, str]] | None,
) -> Metadata:
    metadata = Metadata(metadata)

    if RESET_MASK_HEADER not in metadata:  # type:ignore[comparison-overlap]
        metadata[RESET_MASK_HEADER] = Message.get_full_update_reset_mask(msg).marshal()
    return metadata
