"""Service address resolvers used by the SDK and generated clients.

This module defines a small composable resolver abstraction used to map a
logical service identifier (for example the fully-qualified protobuf service
name) to a concrete network address or address template used for routing RPCs.

Common usage patterns:

- `Single` maps a single explicit id to an address.
- `Prefix` maps any service id beginning with a prefix to an address.
- `Basic` is a convenience factory that chooses `Single` or `Prefix`
    depending on whether the provided id ends with a ``*``.
- `Constant` always returns the same address regardless of id.
- `Conventional` implements a convention-based mapping used by the SDK
    (parses service names like ``nebius.<service>...Service`` and returns
    ``<service>.{domain}`` by default; it also honors a protobuf extension named
    ``api_service_name`` when present).
- `Chain` composes multiple resolvers and returns the first match.
- `Cached` memoizes results from another resolver.
- `TemplateExpander` applies simple string substitutions on resolved
    addresses (useful for replacing templated placeholders such as
    ``{domain}``).

All resolvers implement :class:`Resolver` and raise :class:`UnknownServiceError`
when a service id cannot be resolved.
"""

from abc import ABC, abstractmethod
from logging import getLogger

from .error import SDKError

log = getLogger(__name__)


class UnknownServiceError(SDKError):
    """Raised when a resolver cannot map a service id to an address.

    The exception is used to signal non-matching resolvers in composition
    chains (for example :class:`Chain`). The message contains the original
    service id that could not be resolved.

    :param id: The service id that could not be resolved.
    """

    def __init__(self, id: str) -> None:
        super().__init__(f"Unknown service: {id}")


class Resolver(ABC):
    """Abstract resolver interface.

    Implementations map a logical ``service_id`` (typically a fully
    qualified protobuf service name such as ``nebius.foo.v1.FooService``) to a
    concrete address string. Implementations MUST raise
    :class:`UnknownServiceError` when they do not match the provided
    ``service_id``; callers can compose resolvers (for example via
    :class:`Chain`) to try multiple strategies.

    The returned address is typically a hostname or an address template
    (for example ``service.{domain}``) which may be further processed by
    higher-level code.
    """

    @abstractmethod
    def resolve(self, service_id: str) -> str:
        """Return the resolved address for ``service_id`` or raise
        :class:`UnknownServiceError` if the resolver does not apply.

        :param service_id: Logical service identifier to resolve.
        :returns: Address string or template.
        :raises UnknownServiceError: when the resolver does not match.
        """
        raise NotImplementedError("Method not implemented!")


class Basic(Resolver):
    """Convenience resolver that selects `Single` or `Prefix`.

    If the provided `id` ends with a literal ``*`` the instance delegates to a
    :class:`Prefix` resolver (with the trailing star removed). Otherwise it
    delegates to a :class:`Single` resolver. This helper is useful when
    parsing simple configuration entries that allow either a single service id
    or a prefix pattern.

    :param id: Service id or prefix (use trailing ``*`` for prefix).
    :param address: Address or template to return for matching ids.
    """

    _parent: Resolver

    def __init__(self, id: str, address: str) -> None:
        super().__init__()
        if id.endswith("*"):
            log.debug("basic resolver is Prefix resolver")
            self._parent = Prefix(id[:-1], address)
        else:
            log.debug("basic resolver is Single resolver")
            self._parent = Single(id, address)

    def resolve(self, service_id: str) -> str:
        """Delegate resolution to the selected child resolver.

        :param service_id: Service identifier to resolve.
        :returns: Resolved address string.
        :raises UnknownServiceError: If the delegated resolver does not match.
        """
        ret = self._parent.resolve(service_id)
        log.debug(f"basic resolver resolved {service_id} to {ret}")
        return ret


class Constant(Resolver):
    """Resolver that always returns a fixed address.

    Useful for testing or when all services are routed through a single
    endpoint.

    :param address: Address string that will be returned for any id.
    """

    def __init__(self, address: str) -> None:
        super().__init__()
        self._address = address

    def resolve(self, service_id: str) -> str:
        """Return the configured address for any ``service_id``.

        This implementation never raises :class:`UnknownServiceError`.

        :param service_id: Service identifier to resolve (ignored).
        :returns: The configured address.
        """
        log.debug(f"constant resolver resolved {service_id} to {self._address}")
        return self._address


class Single(Resolver):
    """Resolver that matches a single explicit service id.

    The resolver returns ``address`` only when the provided ``service_id`` is
    exactly equal to the id supplied at construction.

    :param id: Exact service identifier to match.
    :param address: Address to return when the id matches.
    """

    def __init__(self, id: str, address: str) -> None:
        super().__init__()
        self._id = id
        self._address = address

    def resolve(self, service_id: str) -> str:
        """Resolve only when ``service_id`` exactly matches the configured id.

        :param service_id: Service identifier to resolve.
        :returns: The configured address when the id matches.
        :raises UnknownServiceError: when the id does not match.
        """
        if service_id == self._id:
            log.debug(f"single resolver resolved {service_id} to {self._address}")
            return self._address
        log.debug(f"single resolver {service_id} not matches resolver ID")
        raise UnknownServiceError(service_id)


class Prefix(Resolver):
    """Resolver that matches service ids by prefix.

    The resolver returns the configured address when ``service_id`` begins
    with the supplied prefix. If it does not match it raises
    :class:`UnknownServiceError`.

    :param prefix: Leading string that matching service ids must start with.
    :param address: Address to return for matching ids.
    """

    def __init__(self, prefix: str, address: str) -> None:
        super().__init__()
        self._prefix = prefix
        self._address = address

    def resolve(self, service_id: str) -> str:
        """Resolve when ``service_id`` starts with the configured prefix.

        :param service_id: Service identifier to resolve.
        :returns: The configured address when the prefix matches.
        :raises UnknownServiceError: when the prefix does not match.
        """
        if service_id.startswith(self._prefix):
            log.debug(f"prefix resolver {service_id} resolved to {self._address}")
            return self._address
        log.debug(f"prefix resolver {service_id} not matches pattern")
        raise UnknownServiceError(service_id)


class Conventional(Resolver):
    """Convention-based resolver for Nebius services.

    This resolver recognizes service ids that follow the Nebius naming
    convention (for example ``nebius.foo.v1.FooService``). It extracts the
    service short-name (``foo`` in the example) and returns a templated
    address ``<service>.{domain}``.

    If the protobuf service descriptor defines the ``api_service_name``
    extension the extension value will be used as the service short-name
    instead of the second dot-separated path element.
    """

    def resolve(self, service_id: str) -> str:
        """Resolve a conventional Nebius service id to ``<service>.{domain}``.

        :param service_id: Service identifier to resolve.
        :returns: The resolved address template.
        :raises UnknownServiceError: when the provided id does not follow the
            recognized convention.
        """
        parts = service_id.split(".")
        if len(parts) < 3 or parts[0] != "nebius" or not parts[-1].endswith("Service"):
            raise UnknownServiceError(service_id)
        service_name = parts[1]
        try:
            from google.protobuf.descriptor import ServiceDescriptor
            from google.protobuf.descriptor_pb2 import ServiceOptions
            from google.protobuf.descriptor_pool import (
                Default,  # type: ignore[unused-ignore]
                DescriptorPool,
            )

            from nebius.api.nebius.annotations_pb2 import api_service_name

            pool: DescriptorPool = Default()  # type: ignore[unused-ignore,no-untyped-call]
            service_descriptor: ServiceDescriptor = pool.FindServiceByName(service_id)  # type: ignore[unused-ignore,no-untyped-call]
            opts: ServiceOptions = service_descriptor.GetOptions()  # type: ignore[unused-ignore]
            if opts.Extensions[api_service_name] != "":  # type: ignore[unused-ignore,index]
                service_name = opts.Extensions[api_service_name]  # type: ignore[unused-ignore,index]
        except KeyError:
            pass
        ret = service_name + ".{domain}"  # type: ignore[unused-ignore]
        log.debug(f"conventional resolver {service_id} resolved to {ret}")

        return ret  # type: ignore[unused-ignore]


class Chain(Resolver):
    """Compose several resolvers and return the first successful result.

    The chain tries each resolver in order; resolvers that do not match are
    expected to raise :class:`UnknownServiceError` and are skipped. If none of
    the resolvers match the chain raises :class:`UnknownServiceError`.

    :param resolvers: Resolver instances tried in order until one succeeds.
    """

    def __init__(self, *resolvers: Resolver) -> None:
        super().__init__()
        self._resolvers = resolvers

    def resolve(self, service_id: str) -> str:
        """Attempt resolution using each chained resolver.

        :param service_id: Service identifier to resolve.
        :returns: The address returned by the first matching resolver.
        :raises UnknownServiceError: if no chained resolver returns a result.
        """
        for resolver in self._resolvers:
            try:
                ret = resolver.resolve(service_id)
                log.debug(f"chain resolver {service_id} resolved to {ret}")
                return ret
            except UnknownServiceError:
                continue
        log.debug(f"chain resolver {service_id} didn't match any resolver in chain")
        raise UnknownServiceError(service_id)


class Cached(Resolver):
    """Memoizing resolver that caches results from another resolver.

    The cache is in-memory and process-local. It grows as new service ids are
    resolved and never evicts entries (suitable for small sets of services).

    :param next: Underlying resolver used when a value is not cached.
    """

    def __init__(self, next: Resolver) -> None:
        super().__init__()
        self._cache = dict[str, str]()
        self._next = next

    def resolve(self, service_id: str) -> str:
        """Return a cached address or query the underlying resolver.

        :param service_id: Service identifier to resolve.
        :returns: The cached or newly resolved address.
        :raises UnknownServiceError: propagated from the underlying resolver
            when it does not match the id.
        """
        if service_id in self._cache:
            log.debug(
                f"cached resolver {service_id} resolved to {self._cache[service_id]}"
            )
            return self._cache[service_id]

        addr = self._next.resolve(service_id)
        self._cache[service_id] = addr
        log.debug(f"cached resolver {service_id} resolved to {addr} and saved in cache")
        return addr


class TemplateExpander(Resolver):
    """Resolver that applies simple string substitutions to results.

    The resolver delegates to an underlying resolver and then replaces all
    occurrences of each key in ``substitutions`` with its corresponding
    value in the returned address string. This is intended for simple
    templating (for example replacing ``{domain}``).

    :param substitutions: Mapping of substrings to replace in the resolved
        address.
    :param next: Underlying resolver to obtain the initial address.
    """

    def __init__(self, substitutions: dict[str, str], next: Resolver) -> None:
        super().__init__()
        self._substitutions = substitutions
        self._next = next

    def resolve(self, service_id: str) -> str:
        """Resolve via the underlying resolver and apply substitutions.

        :param service_id: Service identifier to resolve.
        :returns: The address after performing the configured replacements.
        :raises UnknownServiceError: propagated from the underlying resolver
            when it does not match the id.
        """
        addr = self._next.resolve(service_id)
        for find, replace in self._substitutions.items():
            addr = addr.replace(find, replace)
        log.debug(f"template expander {service_id} resolved to {addr}")
        return addr
