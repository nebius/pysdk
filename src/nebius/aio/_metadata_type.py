from collections.abc import Sequence

from grpc.aio._metadata import Metadata

MetadataKey = str
MetadatumType = tuple[MetadataKey, str | bytes]
MetadataType = Metadata | Sequence[MetadatumType]
