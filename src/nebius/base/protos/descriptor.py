from abc import ABC
from typing import Generic, Optional, Type, TypeVar, Union

import google.protobuf.descriptor as pb

# Define the TypeVar for supported descriptor types
T = TypeVar("T", pb.EnumDescriptor, pb.Descriptor, pb.OneofDescriptor)


class DescriptorWrap(ABC, Generic[T]):
    def __init__(
        self,
        name: str,
        file_descriptor: pb.FileDescriptor,
        expected_type: Type[T],
    ) -> None:
        self._name = name
        self._file_descriptor = file_descriptor
        self._expected_type = expected_type
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
        self, container: Union[pb.FileDescriptor, pb.Descriptor], name: str
    ) -> Optional[Union[pb.Descriptor, pb.EnumDescriptor, pb.OneofDescriptor]]:
        """
        Recursively searches for the descriptor in the given container (file or message)
        """
        # Check for top-level messages
        if isinstance(container, pb.FileDescriptor):
            for enum in container.enum_types_by_name.values():
                if enum.full_name == name:
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
                    return nested_enum
            for oneof in container.oneofs:
                if oneof.full_name == name:
                    return oneof

        return None
