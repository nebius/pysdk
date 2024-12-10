from abc import ABC, abstractmethod
from logging import getLogger

from .error import SDKError

log = getLogger(__name__)


class UnknownServiceError(SDKError):
    def __init__(self, id: str) -> None:
        super().__init__(f"Unknown service: {id}")


class Resolver(ABC):
    @abstractmethod
    def resolve(self, service_id: str) -> str:
        """Receive address of the service by its ID

        Args:
            service_id (str): service ID

        Returns:
            str: address of the service
        """
        raise NotImplementedError("Method not implemented!")


class Basic(Resolver):
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
        ret = self._parent.resolve(service_id)
        log.debug(f"basic resolver resolved {service_id} to {ret}")
        return ret


class Constant(Resolver):
    def __init__(self, address: str) -> None:
        super().__init__()
        self._address = address

    def resolve(self, service_id: str) -> str:
        log.debug(f"constant resolver resolved {service_id} to {self._address}")
        return self._address


class Single(Resolver):
    def __init__(self, id: str, address: str) -> None:
        super().__init__()
        self._id = id
        self._address = address

    def resolve(self, service_id: str) -> str:
        if service_id == self._id:
            log.debug(f"single resolver resolved {service_id} to {self._address}")
            return self._address
        log.debug(f"single resolver {service_id} not matches resolver ID")
        raise UnknownServiceError(service_id)


class Prefix(Resolver):
    def __init__(self, prefix: str, address: str) -> None:
        super().__init__()
        self._prefix = prefix
        self._address = address

    def resolve(self, service_id: str) -> str:
        if service_id.startswith(self._prefix):
            log.debug(f"prefix resolver {service_id} resolved to {self._address}")
            return self._address
        log.debug(f"prefix resolver {service_id} not matches pattern")
        raise UnknownServiceError(service_id)


class Conventional(Resolver):
    def resolve(self, service_id: str) -> str:
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
    def __init__(self, *resolvers: Resolver) -> None:
        super().__init__()
        self._resolvers = resolvers

    def resolve(self, service_id: str) -> str:
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
    def __init__(self, next: Resolver) -> None:
        super().__init__()
        self._cache = dict[str, str]()
        self._next = next

    def resolve(self, service_id: str) -> str:
        if service_id in self._cache:
            log.debug(
                f"cached resolver {service_id} resolved to "
                f"{self._cache[service_id]}"
            )
            return self._cache[service_id]

        addr = self._next.resolve(service_id)
        self._cache[service_id] = addr
        log.debug(f"cached resolver {service_id} resolved to {addr} and saved in cache")
        return addr


class TemplateExpander(Resolver):
    def __init__(self, substitutions: dict[str, str], next: Resolver) -> None:
        super().__init__()
        self._substitutions = substitutions
        self._next = next

    def resolve(self, service_id: str) -> str:
        addr = self._next.resolve(service_id)
        for find, replace in self._substitutions.items():
            addr = addr.replace(find, replace)
        log.debug(f"template expander {service_id} resolved to {addr}")
        return addr
