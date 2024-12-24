from dataclasses import dataclass

from .pygen import ImportedSymbol


@dataclass
class WellKnown:
    proto_name: str
    from_func: ImportedSymbol
    to_func: ImportedSymbol
    proto_class: ImportedSymbol
    python_class: ImportedSymbol
    mask_func: ImportedSymbol


converter_list = [
    WellKnown(
        proto_name=".google.protobuf.Timestamp",
        proto_class=ImportedSymbol("Timestamp", "google.protobuf.timestamp_pb2"),
        python_class=ImportedSymbol("datetime", "datetime"),
        from_func=ImportedSymbol("from_timestamp", "nebius.base.protos.well_known"),
        to_func=ImportedSymbol("to_timestamp", "nebius.base.protos.well_known"),
        mask_func=ImportedSymbol("ts_mask", "nebius.base.protos.well_known"),
    ),
    WellKnown(
        proto_name=".google.protobuf.Duration",
        proto_class=ImportedSymbol("Duration", "google.protobuf.duration_pb2"),
        python_class=ImportedSymbol("timedelta", "datetime"),
        from_func=ImportedSymbol("from_duration", "nebius.base.protos.well_known"),
        to_func=ImportedSymbol("to_duration", "nebius.base.protos.well_known"),
        mask_func=ImportedSymbol("duration_mask", "nebius.base.protos.well_known"),
    ),
    WellKnown(
        proto_name=".google.rpc.Status",
        proto_class=ImportedSymbol("Status", "google.rpc.status_pb2"),
        python_class=ImportedSymbol("RequestStatus", "nebius.aio.request_status"),
        from_func=ImportedSymbol(
            "request_status_from_rpc_status", "nebius.aio.request_status"
        ),
        to_func=ImportedSymbol(
            "request_status_to_rpc_status", "nebius.aio.request_status"
        ),
        mask_func=ImportedSymbol("status_mask", "nebius.base.protos.well_known"),
    ),
]

converter_dict = {k.proto_name: k for k in converter_list}
