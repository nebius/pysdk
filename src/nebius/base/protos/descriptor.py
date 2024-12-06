from abc import ABC
from typing import Generic, TypeVar

import google.protobuf.descriptor as pb

# Define the TypeVar for supported descriptor types
T = TypeVar(
    "T", pb.EnumDescriptor, pb.Descriptor, pb.OneofDescriptor, pb.ServiceDescriptor
)


class DescriptorWrap(ABC, Generic[T]):
    def __init__(
        self,
        name: str,
        file_descriptor: pb.FileDescriptor,
        expected_type: type[T],
    ) -> None:
        if name[0] == ".":
            name = name[1:]
        self._name = name
        self._file_descriptor = file_descriptor
        self._expected_type: type[T] = expected_type
        self._descriptor: T | None = None

    def __call__(self) -> T:
        """Retrieve the descriptor of the specified type using the fully qualified
        name."""
        if self._descriptor is not None:
            return self._descriptor
        descriptor = self._find_descriptor(self._file_descriptor, self._name)
        if descriptor is None:
            raise ValueError(f"No descriptor found for name {self._name}")
        if not isinstance(descriptor, self._expected_type):
            raise TypeError(
                f"Descriptor {self._name} is of type {type(descriptor).__name__}, "
                f"expected {self._expected_type.__name__}"
            )
        self._descriptor = descriptor
        return descriptor

    def _find_descriptor(
        self, container: pb.FileDescriptor | pb.Descriptor, name: str
    ) -> (
        pb.Descriptor
        | pb.EnumDescriptor
        | pb.OneofDescriptor
        | pb.ServiceDescriptor
        | None
    ):
        """
        Recursively searches for the descriptor in the given container (file or message)
        """
        # Check for top-level messages
        if isinstance(container, pb.FileDescriptor):
            for srv in container.services_by_name.values():
                if srv.full_name == name:
                    if not isinstance(srv, pb.ServiceDescriptor):
                        raise ValueError(f"Pool returned unexpected type {type(srv)}")
                    return srv
            for enum in container.enum_types_by_name.values():
                if enum.full_name == name:
                    if not isinstance(enum, pb.EnumDescriptor):
                        raise ValueError(f"Pool returned unexpected type {type(enum)}")
                    return enum
            for message in container.message_types_by_name.values():
                found = self._find_descriptor(message, name)
                if found:
                    return found

        # Check for nested messages and enums in a message
        else:
            if container.full_name == name:
                return container
            for nested_message in container.nested_types:
                found = self._find_descriptor(nested_message, name)
                if found:
                    return found
            for nested_enum in container.enum_types:
                if nested_enum.full_name == name:
                    if not isinstance(nested_enum, pb.EnumDescriptor):
                        raise ValueError(
                            f"Pool returned unexpected type {type(nested_enum)}"
                        )
                    return nested_enum
            for oneof in container.oneofs:
                if oneof.full_name == name:
                    if not isinstance(oneof, pb.OneofDescriptor):
                        raise ValueError(f"Pool returned unexpected type {type(oneof)}")
                    return oneof

        return None
