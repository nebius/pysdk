"""gRPC keepalive configuration shared by SDK channels.

Channel constructors accept ``keepalive`` as ``None``/``True`` for SDK defaults,
``False`` to disable SDK keepalive, or explicit :class:`KeepaliveOptions` /
mapping overrides. With the default ``None`` value the SDK reads
``NEBIUS_GRPC_KEEPALIVE_*`` environment variables. Explicit constructor options
ignore those environment variables and use SDK defaults for omitted fields.

The resolved configuration is converted into Python gRPC channel arguments by
:func:`keepalive_channel_options`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from os import environ
from re import Match, compile

from grpc.aio._typing import ChannelArgumentType

DEFAULT_KEEPALIVE_TIME_MS = 20_000
"""Default interval between client keepalive pings, in milliseconds."""

DEFAULT_KEEPALIVE_TIMEOUT_MS = 10_000
"""Default timeout for a keepalive ping response, in milliseconds."""

DEFAULT_KEEPALIVE_PERMIT_WITHOUT_STREAM = True
"""Whether keepalive pings are sent without active RPC streams."""

ENV_GRPC_KEEPALIVE_TIME = "NEBIUS_GRPC_KEEPALIVE_TIME"
ENV_GRPC_KEEPALIVE_TIMEOUT = "NEBIUS_GRPC_KEEPALIVE_TIMEOUT"
ENV_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM = "NEBIUS_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM"

_DURATION_PART_RE = compile(r"([0-9]+(?:\.[0-9]*)?|\.[0-9]+)(ns|us|µs|μs|ms|s|m|h)")
_UNIT_TO_NANOSECONDS = {
    "ns": Decimal(1),
    "us": Decimal(1_000),
    "µs": Decimal(1_000),
    "μs": Decimal(1_000),
    "ms": Decimal(1_000_000),
    "s": Decimal(1_000_000_000),
    "m": Decimal(60_000_000_000),
    "h": Decimal(3_600_000_000_000),
}
_NANOSECONDS_IN_MILLISECOND = Decimal(1_000_000)


@dataclass(frozen=True)
class KeepaliveOptions:
    """Explicit keepalive overrides for :class:`nebius.aio.channel.Channel`.

    Passing explicit options ignores ``NEBIUS_GRPC_KEEPALIVE_*`` environment
    variables. Omitted fields use SDK defaults. Set ``time_ms`` to ``0`` or pass
    ``keepalive=False`` to the channel constructor to disable SDK keepalive.

    :param time_ms: Interval between client keepalive pings in milliseconds.
        ``0`` disables SDK keepalive.
    :param timeout_ms: Timeout for a keepalive ping response in milliseconds.
    :param permit_without_stream: Whether pings may be sent when there are no
        active RPC streams.
    """

    time_ms: int | None = None
    timeout_ms: int | None = None
    permit_without_stream: bool | None = None


@dataclass(frozen=True)
class KeepaliveConfig:
    """Resolved keepalive configuration."""

    enabled: bool
    time_ms: int
    timeout_ms: int
    permit_without_stream: bool


def default_keepalive_config() -> KeepaliveConfig:
    """Return the GoSDK-compatible default keepalive configuration."""

    return KeepaliveConfig(
        enabled=True,
        time_ms=DEFAULT_KEEPALIVE_TIME_MS,
        timeout_ms=DEFAULT_KEEPALIVE_TIMEOUT_MS,
        permit_without_stream=DEFAULT_KEEPALIVE_PERMIT_WITHOUT_STREAM,
    )


def keepalive_config_from_env(
    env: Mapping[str, str | None] | None = None,
) -> KeepaliveConfig:
    """Resolve keepalive configuration from environment variables.

    Durations use Go-style syntax such as ``20s``, ``500ms``, or ``1m30s``.
    Boolean values follow Go ``strconv.ParseBool`` accepted values.
    """

    env = environ if env is None else env
    cfg = default_keepalive_config()
    enabled = cfg.enabled
    time_ms = cfg.time_ms
    timeout_ms = cfg.timeout_ms
    permit_without_stream = cfg.permit_without_stream

    keepalive_time = _lookup_keepalive_env(env, ENV_GRPC_KEEPALIVE_TIME)
    if keepalive_time is not None:
        time_ms = parse_go_duration_ms(ENV_GRPC_KEEPALIVE_TIME, keepalive_time)
        enabled = time_ms != 0

    keepalive_timeout = _lookup_keepalive_env(env, ENV_GRPC_KEEPALIVE_TIMEOUT)
    if keepalive_timeout is not None:
        timeout_ms = parse_go_duration_ms(ENV_GRPC_KEEPALIVE_TIMEOUT, keepalive_timeout)

    permit = _lookup_keepalive_env(env, ENV_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM)
    if permit is not None:
        permit_without_stream = parse_go_bool(
            ENV_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM, permit
        )

    cfg = KeepaliveConfig(
        enabled=enabled,
        time_ms=time_ms,
        timeout_ms=timeout_ms,
        permit_without_stream=permit_without_stream,
    )
    validate_keepalive_config(cfg)
    return cfg


def keepalive_config_from_options(
    options: KeepaliveOptions | Mapping[str, object] | bool | None,
) -> KeepaliveConfig:
    """Resolve keepalive configuration from explicit constructor options.

    ``None`` reads environment variables, ``True`` forces SDK defaults, and
    ``False`` disables SDK keepalive. Mappings accept both snake_case and
    camelCase keys: ``time_ms``/``timeMs``, ``timeout_ms``/``timeoutMs``, and
    ``permit_without_stream``/``permitWithoutStream``.
    """

    if options is False:
        cfg = default_keepalive_config()
        return KeepaliveConfig(
            enabled=False,
            time_ms=0,
            timeout_ms=cfg.timeout_ms,
            permit_without_stream=cfg.permit_without_stream,
        )
    if options is None:
        return keepalive_config_from_env()
    if options is True:
        cfg = default_keepalive_config()
        validate_keepalive_config(cfg)
        return cfg

    cfg = default_keepalive_config()
    time_ms = cfg.time_ms
    timeout_ms = cfg.timeout_ms
    permit_without_stream = cfg.permit_without_stream

    if isinstance(options, KeepaliveOptions):
        explicit_time_ms = options.time_ms
        explicit_timeout_ms = options.timeout_ms
        explicit_permit = options.permit_without_stream
    else:
        explicit_time_ms = _mapping_keepalive_int(options, "time_ms", "timeMs")
        explicit_timeout_ms = _mapping_keepalive_int(options, "timeout_ms", "timeoutMs")
        explicit_permit = _mapping_keepalive_bool(
            options, "permit_without_stream", "permitWithoutStream"
        )

    if explicit_time_ms is not None:
        _assert_valid_keepalive_ms("keepalive.time_ms", explicit_time_ms, True)
        time_ms = explicit_time_ms
    if explicit_timeout_ms is not None:
        _assert_valid_keepalive_ms("keepalive.timeout_ms", explicit_timeout_ms, True)
        timeout_ms = explicit_timeout_ms
    if explicit_permit is not None:
        permit_without_stream = explicit_permit

    resolved = KeepaliveConfig(
        enabled=time_ms != 0,
        time_ms=time_ms,
        timeout_ms=timeout_ms,
        permit_without_stream=permit_without_stream,
    )
    validate_keepalive_config(resolved)
    return resolved


def keepalive_channel_options(cfg: KeepaliveConfig) -> ChannelArgumentType:
    """Convert keepalive config to Python gRPC channel options."""

    if not cfg.enabled:
        return []
    return [
        ("grpc.keepalive_time_ms", cfg.time_ms),
        ("grpc.keepalive_timeout_ms", cfg.timeout_ms),
        (
            "grpc.keepalive_permit_without_calls",
            1 if cfg.permit_without_stream else 0,
        ),
    ]


def parse_go_duration_ms(name: str, value: str) -> int:
    """Parse a subset of Go ``time.ParseDuration`` syntax into milliseconds."""

    value = value.strip()
    if value == "":
        raise ValueError(f"{name} is empty")
    if value == "0":
        return 0

    sign = 1
    if value[0] in ("+", "-"):
        sign = -1 if value[0] == "-" else 1
        value = value[1:]
    if value == "":
        raise ValueError(f"parse {name}: invalid duration")

    pos = 0
    total_ns = Decimal(0)
    while pos < len(value):
        match = _DURATION_PART_RE.match(value, pos)
        if match is None:
            raise ValueError(f"parse {name}: invalid duration")
        total_ns += _duration_part_ns(match)
        pos = match.end()

    total_ns *= sign
    if total_ns < 0:
        raise ValueError(f"{name} must not be negative")
    if total_ns == 0:
        return 0
    return int(
        (total_ns / _NANOSECONDS_IN_MILLISECOND).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def parse_go_bool(name: str, value: str) -> bool:
    """Parse Go ``strconv.ParseBool`` accepted values."""

    value = value.strip()
    if value in ("1", "t", "T", "TRUE", "true", "True"):
        return True
    if value in ("0", "f", "F", "FALSE", "false", "False"):
        return False
    raise ValueError(f"parse {name}: invalid boolean {value!r}")


def validate_keepalive_config(cfg: KeepaliveConfig) -> None:
    """Validate resolved keepalive values."""

    _assert_valid_keepalive_ms("keepalive.time_ms", cfg.time_ms, True)
    _assert_valid_keepalive_ms("keepalive.timeout_ms", cfg.timeout_ms, True)
    if cfg.enabled and cfg.timeout_ms <= 0:
        raise ValueError(
            f"{ENV_GRPC_KEEPALIVE_TIMEOUT} must be positive when keepalive is enabled"
        )


def _duration_part_ns(match: Match[str]) -> Decimal:
    try:
        value = Decimal(match.group(1))
    except InvalidOperation as err:
        raise ValueError("invalid duration value") from err
    return value * _UNIT_TO_NANOSECONDS[match.group(2)]


def _lookup_keepalive_env(env: Mapping[str, str | None], name: str) -> str | None:
    value = env.get(name)
    if value is None:
        return None
    value = value.strip()
    return value if value != "" else None


def _assert_valid_keepalive_ms(name: str, value: int, allow_zero: bool) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer number of milliseconds")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    if value == 0 and not allow_zero:
        raise ValueError(f"{name} must be positive")


def _mapping_keepalive_int(
    options: Mapping[str, object], snake_name: str, camel_name: str
) -> int | None:
    value = options.get(snake_name, options.get(camel_name))
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(
            f"keepalive.{snake_name} must be an integer number of milliseconds"
        )
    return value


def _mapping_keepalive_bool(
    options: Mapping[str, object], snake_name: str, camel_name: str
) -> bool | None:
    value = options.get(snake_name, options.get(camel_name))
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeError(f"keepalive.{snake_name} must be bool")
    return value
