# 
# Generated by the nebius.base.protos.compiler.  DO NOT EDIT!
# 

import builtins as builtins
import collections.abc as abc
import google.protobuf.descriptor as descriptor_1
import google.protobuf.message as message_1
import grpc as grpc
import nebius.aio.client as client
import nebius.aio.operation as operation
import nebius.aio.request as request_1
import nebius.api.nebius.applications.v1alpha1.k8s_release_pb2 as k8s_release_pb2
import nebius.api.nebius.applications.v1alpha1.k8s_release_service_pb2 as k8s_release_service_pb2
import nebius.api.nebius.common.v1 as v1_1
import nebius.api.nebius.common.v1.metadata_pb2 as metadata_pb2
import nebius.api.nebius.common.v1.operation_pb2 as operation_pb2
import nebius.base.fieldmask_protobuf as fieldmask_protobuf
import nebius.base.protos.descriptor as descriptor
import nebius.base.protos.pb_classes as pb_classes
import nebius.base.protos.pb_enum as pb_enum
import nebius.base.protos.unset as unset
#@ local imports here @#

# file: nebius/applications/v1alpha1/k8s_release.proto
class K8sRelease(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_pb2.K8sRelease
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.K8sRelease",k8s_release_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        metadata: "v1_1.ResourceMetadata|metadata_pb2.ResourceMetadata|None|unset.UnsetType" = unset.Unset,
        spec: "K8sReleaseSpec|k8s_release_pb2.K8sReleaseSpec|None|unset.UnsetType" = unset.Unset,
        status: "K8sReleaseStatus|k8s_release_pb2.K8sReleaseStatus|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(metadata, unset.UnsetType):
            self.metadata = metadata
        if not isinstance(spec, unset.UnsetType):
            self.spec = spec
        if not isinstance(status, unset.UnsetType):
            self.status = status
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "metadata",
            "spec",
            "status",
        ]
    
    @builtins.property
    def metadata(self) -> "v1_1.ResourceMetadata":
        return super()._get_field("metadata", explicit_presence=False,
        wrap=v1_1.ResourceMetadata,
        )
    @metadata.setter
    def metadata(self, value: "v1_1.ResourceMetadata|metadata_pb2.ResourceMetadata|None") -> None:
        return super()._set_field("metadata",value,explicit_presence=False,
        )
    
    @builtins.property
    def spec(self) -> "K8sReleaseSpec":
        return super()._get_field("spec", explicit_presence=False,
        wrap=K8sReleaseSpec,
        )
    @spec.setter
    def spec(self, value: "K8sReleaseSpec|k8s_release_pb2.K8sReleaseSpec|None") -> None:
        return super()._set_field("spec",value,explicit_presence=False,
        )
    
    @builtins.property
    def status(self) -> "K8sReleaseStatus":
        return super()._get_field("status", explicit_presence=False,
        wrap=K8sReleaseStatus,
        )
    @status.setter
    def status(self, value: "K8sReleaseStatus|k8s_release_pb2.K8sReleaseStatus|None") -> None:
        return super()._set_field("status",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "metadata":"metadata",
        "spec":"spec",
        "status":"status",
    }
    
class K8sReleaseSpec(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_pb2.K8sReleaseSpec
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.K8sReleaseSpec",k8s_release_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    class SetEntry(pb_classes.Message):
        __PB2_CLASS__ = k8s_release_pb2.K8sReleaseSpec.SetEntry
        __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.K8sReleaseSpec.SetEntry",k8s_release_pb2.DESCRIPTOR,descriptor_1.Descriptor)
        __mask_functions__ = {
        }
        
        def __init__(
            self,
            initial_message: message_1.Message|None = None,
            *,
            key: "builtins.str|None|unset.UnsetType" = unset.Unset,
            value: "builtins.str|None|unset.UnsetType" = unset.Unset,
        ) -> None:
            super().__init__(initial_message)
            if not isinstance(key, unset.UnsetType):
                self.key = key
            if not isinstance(value, unset.UnsetType):
                self.value = value
        
        def __dir__(self) ->abc.Iterable[builtins.str]:
            return [
                "key",
                "value",
            ]
        
        @builtins.property
        def key(self) -> "builtins.str":
            return super()._get_field("key", explicit_presence=False,
            )
        @key.setter
        def key(self, value: "builtins.str|None") -> None:
            return super()._set_field("key",value,explicit_presence=False,
            )
        
        @builtins.property
        def value(self) -> "builtins.str":
            return super()._get_field("value", explicit_presence=False,
            )
        @value.setter
        def value(self, value: "builtins.str|None") -> None:
            return super()._set_field("value",value,explicit_presence=False,
            )
        
        __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
            "key":"key",
            "value":"value",
        }
        
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        cluster_id: "builtins.str|None|unset.UnsetType" = unset.Unset,
        product_slug: "builtins.str|None|unset.UnsetType" = unset.Unset,
        namespace: "builtins.str|None|unset.UnsetType" = unset.Unset,
        application_name: "builtins.str|None|unset.UnsetType" = unset.Unset,
        values: "builtins.str|None|unset.UnsetType" = unset.Unset,
        set: "abc.Mapping[builtins.str,builtins.str]|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(cluster_id, unset.UnsetType):
            self.cluster_id = cluster_id
        if not isinstance(product_slug, unset.UnsetType):
            self.product_slug = product_slug
        if not isinstance(namespace, unset.UnsetType):
            self.namespace = namespace
        if not isinstance(application_name, unset.UnsetType):
            self.application_name = application_name
        if not isinstance(values, unset.UnsetType):
            self.values = values
        if not isinstance(set, unset.UnsetType):
            self.set = set
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "cluster_id",
            "product_slug",
            "namespace",
            "application_name",
            "values",
            "set",
            "SetEntry",
        ]
    
    @builtins.property
    def cluster_id(self) -> "builtins.str":
        return super()._get_field("cluster_id", explicit_presence=False,
        )
    @cluster_id.setter
    def cluster_id(self, value: "builtins.str|None") -> None:
        return super()._set_field("cluster_id",value,explicit_presence=False,
        )
    
    @builtins.property
    def product_slug(self) -> "builtins.str":
        return super()._get_field("product_slug", explicit_presence=False,
        )
    @product_slug.setter
    def product_slug(self, value: "builtins.str|None") -> None:
        return super()._set_field("product_slug",value,explicit_presence=False,
        )
    
    @builtins.property
    def namespace(self) -> "builtins.str":
        return super()._get_field("namespace", explicit_presence=False,
        )
    @namespace.setter
    def namespace(self, value: "builtins.str|None") -> None:
        return super()._set_field("namespace",value,explicit_presence=False,
        )
    
    @builtins.property
    def application_name(self) -> "builtins.str":
        return super()._get_field("application_name", explicit_presence=False,
        )
    @application_name.setter
    def application_name(self, value: "builtins.str|None") -> None:
        return super()._set_field("application_name",value,explicit_presence=False,
        )
    
    @builtins.property
    def values(self) -> "builtins.str":
        return super()._get_field("values", explicit_presence=False,
        )
    @values.setter
    def values(self, value: "builtins.str|None") -> None:
        return super()._set_field("values",value,explicit_presence=False,
        )
    
    @builtins.property
    def set(self) -> "abc.MutableMapping[builtins.str,builtins.str]":
        return super()._get_field("set", explicit_presence=False,
        wrap=pb_classes.Map,
        )
    @set.setter
    def set(self, value: "abc.Mapping[builtins.str,builtins.str]|None") -> None:
        return super()._set_field("set",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "cluster_id":"cluster_id",
        "product_slug":"product_slug",
        "namespace":"namespace",
        "application_name":"application_name",
        "values":"values",
        "set":"set",
        "SetEntry":"SetEntry",
    }
    
class K8sReleaseStatus(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_pb2.K8sReleaseStatus
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.K8sReleaseStatus",k8s_release_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    class State(pb_enum.Enum):
        __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.EnumDescriptor](".nebius.applications.v1alpha1.K8sReleaseStatus.State",k8s_release_pb2.DESCRIPTOR,descriptor_1.EnumDescriptor)
        UNSPECIFIED = 0
        CREATED = 1
        RUNNING = 2
        DEPLOYED = 3
        FAILED = 4
        INSTALLING = 5
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        state: "K8sReleaseStatus.State|k8s_release_pb2.K8sReleaseStatus.State|None|unset.UnsetType" = unset.Unset,
        error_message: "builtins.str|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(state, unset.UnsetType):
            self.state = state
        if not isinstance(error_message, unset.UnsetType):
            self.error_message = error_message
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "state",
            "error_message",
            "State",
        ]
    
    @builtins.property
    def state(self) -> "K8sReleaseStatus.State":
        return super()._get_field("state", explicit_presence=False,
        wrap=K8sReleaseStatus.State,
        )
    @state.setter
    def state(self, value: "K8sReleaseStatus.State|k8s_release_pb2.K8sReleaseStatus.State|None") -> None:
        return super()._set_field("state",value,explicit_presence=False,
        )
    
    @builtins.property
    def error_message(self) -> "builtins.str":
        return super()._get_field("error_message", explicit_presence=False,
        )
    @error_message.setter
    def error_message(self, value: "builtins.str|None") -> None:
        return super()._set_field("error_message",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "state":"state",
        "error_message":"error_message",
        "State":"State",
    }
    
# file: nebius/applications/v1alpha1/k8s_release_service.proto
class GetK8sReleaseRequest(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_service_pb2.GetK8sReleaseRequest
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.GetK8sReleaseRequest",k8s_release_service_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        id: "builtins.str|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(id, unset.UnsetType):
            self.id = id
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "id",
        ]
    
    @builtins.property
    def id(self) -> "builtins.str":
        return super()._get_field("id", explicit_presence=False,
        )
    @id.setter
    def id(self, value: "builtins.str|None") -> None:
        return super()._set_field("id",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "id":"id",
    }
    
class ListK8sReleasesRequest(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_service_pb2.ListK8sReleasesRequest
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.ListK8sReleasesRequest",k8s_release_service_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        parent_id: "builtins.str|None|unset.UnsetType" = unset.Unset,
        page_size: "builtins.int|None|unset.UnsetType" = unset.Unset,
        page_token: "builtins.str|None|unset.UnsetType" = unset.Unset,
        filter: "builtins.str|None|unset.UnsetType" = unset.Unset,
        cluster_id: "builtins.str|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(parent_id, unset.UnsetType):
            self.parent_id = parent_id
        if not isinstance(page_size, unset.UnsetType):
            self.page_size = page_size
        if not isinstance(page_token, unset.UnsetType):
            self.page_token = page_token
        if not isinstance(filter, unset.UnsetType):
            self.filter = filter
        if not isinstance(cluster_id, unset.UnsetType):
            self.cluster_id = cluster_id
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "parent_id",
            "page_size",
            "page_token",
            "filter",
            "cluster_id",
        ]
    
    @builtins.property
    def parent_id(self) -> "builtins.str":
        return super()._get_field("parent_id", explicit_presence=False,
        )
    @parent_id.setter
    def parent_id(self, value: "builtins.str|None") -> None:
        return super()._set_field("parent_id",value,explicit_presence=False,
        )
    
    @builtins.property
    def page_size(self) -> "builtins.int":
        return super()._get_field("page_size", explicit_presence=False,
        )
    @page_size.setter
    def page_size(self, value: "builtins.int|None") -> None:
        return super()._set_field("page_size",value,explicit_presence=False,
        )
    
    @builtins.property
    def page_token(self) -> "builtins.str":
        return super()._get_field("page_token", explicit_presence=False,
        )
    @page_token.setter
    def page_token(self, value: "builtins.str|None") -> None:
        return super()._set_field("page_token",value,explicit_presence=False,
        )
    
    @builtins.property
    def filter(self) -> "builtins.str":
        return super()._get_field("filter", explicit_presence=False,
        )
    @filter.setter
    def filter(self, value: "builtins.str|None") -> None:
        return super()._set_field("filter",value,explicit_presence=False,
        )
    
    @builtins.property
    def cluster_id(self) -> "builtins.str":
        return super()._get_field("cluster_id", explicit_presence=False,
        )
    @cluster_id.setter
    def cluster_id(self, value: "builtins.str|None") -> None:
        return super()._set_field("cluster_id",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "parent_id":"parent_id",
        "page_size":"page_size",
        "page_token":"page_token",
        "filter":"filter",
        "cluster_id":"cluster_id",
    }
    
class CreateK8sReleaseRequest(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_service_pb2.CreateK8sReleaseRequest
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.CreateK8sReleaseRequest",k8s_release_service_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        metadata: "v1_1.ResourceMetadata|metadata_pb2.ResourceMetadata|None|unset.UnsetType" = unset.Unset,
        spec: "K8sReleaseSpec|k8s_release_pb2.K8sReleaseSpec|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(metadata, unset.UnsetType):
            self.metadata = metadata
        if not isinstance(spec, unset.UnsetType):
            self.spec = spec
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "metadata",
            "spec",
        ]
    
    @builtins.property
    def metadata(self) -> "v1_1.ResourceMetadata":
        return super()._get_field("metadata", explicit_presence=False,
        wrap=v1_1.ResourceMetadata,
        )
    @metadata.setter
    def metadata(self, value: "v1_1.ResourceMetadata|metadata_pb2.ResourceMetadata|None") -> None:
        return super()._set_field("metadata",value,explicit_presence=False,
        )
    
    @builtins.property
    def spec(self) -> "K8sReleaseSpec":
        return super()._get_field("spec", explicit_presence=False,
        wrap=K8sReleaseSpec,
        )
    @spec.setter
    def spec(self, value: "K8sReleaseSpec|k8s_release_pb2.K8sReleaseSpec|None") -> None:
        return super()._set_field("spec",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "metadata":"metadata",
        "spec":"spec",
    }
    
class UpdateK8sReleaseRequest(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_service_pb2.UpdateK8sReleaseRequest
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.UpdateK8sReleaseRequest",k8s_release_service_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        metadata: "v1_1.ResourceMetadata|metadata_pb2.ResourceMetadata|None|unset.UnsetType" = unset.Unset,
        spec: "K8sReleaseSpec|k8s_release_pb2.K8sReleaseSpec|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(metadata, unset.UnsetType):
            self.metadata = metadata
        if not isinstance(spec, unset.UnsetType):
            self.spec = spec
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "metadata",
            "spec",
        ]
    
    @builtins.property
    def metadata(self) -> "v1_1.ResourceMetadata":
        return super()._get_field("metadata", explicit_presence=False,
        wrap=v1_1.ResourceMetadata,
        )
    @metadata.setter
    def metadata(self, value: "v1_1.ResourceMetadata|metadata_pb2.ResourceMetadata|None") -> None:
        return super()._set_field("metadata",value,explicit_presence=False,
        )
    
    @builtins.property
    def spec(self) -> "K8sReleaseSpec":
        return super()._get_field("spec", explicit_presence=False,
        wrap=K8sReleaseSpec,
        )
    @spec.setter
    def spec(self, value: "K8sReleaseSpec|k8s_release_pb2.K8sReleaseSpec|None") -> None:
        return super()._set_field("spec",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "metadata":"metadata",
        "spec":"spec",
    }
    
class DeleteK8sReleaseRequest(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_service_pb2.DeleteK8sReleaseRequest
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.DeleteK8sReleaseRequest",k8s_release_service_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        id: "builtins.str|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(id, unset.UnsetType):
            self.id = id
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "id",
        ]
    
    @builtins.property
    def id(self) -> "builtins.str":
        return super()._get_field("id", explicit_presence=False,
        )
    @id.setter
    def id(self, value: "builtins.str|None") -> None:
        return super()._set_field("id",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "id":"id",
    }
    
class ListK8sReleasesResponse(pb_classes.Message):
    __PB2_CLASS__ = k8s_release_service_pb2.ListK8sReleasesResponse
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.Descriptor](".nebius.applications.v1alpha1.ListK8sReleasesResponse",k8s_release_service_pb2.DESCRIPTOR,descriptor_1.Descriptor)
    __mask_functions__ = {
    }
    
    def __init__(
        self,
        initial_message: message_1.Message|None = None,
        *,
        items: "abc.Iterable[K8sRelease]|None|unset.UnsetType" = unset.Unset,
        next_page_token: "builtins.str|None|unset.UnsetType" = unset.Unset,
    ) -> None:
        super().__init__(initial_message)
        if not isinstance(items, unset.UnsetType):
            self.items = items
        if not isinstance(next_page_token, unset.UnsetType):
            self.next_page_token = next_page_token
    
    def __dir__(self) ->abc.Iterable[builtins.str]:
        return [
            "items",
            "next_page_token",
        ]
    
    @builtins.property
    def items(self) -> "abc.MutableSequence[K8sRelease]":
        return super()._get_field("items", explicit_presence=False,
        wrap=pb_classes.Repeated.with_wrap(K8sRelease,None,None),
        )
    @items.setter
    def items(self, value: "abc.Iterable[K8sRelease]|None") -> None:
        return super()._set_field("items",value,explicit_presence=False,
        )
    
    @builtins.property
    def next_page_token(self) -> "builtins.str":
        return super()._get_field("next_page_token", explicit_presence=False,
        )
    @next_page_token.setter
    def next_page_token(self, value: "builtins.str|None") -> None:
        return super()._set_field("next_page_token",value,explicit_presence=False,
        )
    
    __PY_TO_PB2__: builtins.dict[builtins.str,builtins.str] = {
        "items":"items",
        "next_page_token":"next_page_token",
    }
    

class K8sReleaseServiceClient(client.ClientWithOperations[v1_1.Operation,v1_1.OperationServiceClient]):
    __PB2_DESCRIPTOR__ = descriptor.DescriptorWrap[descriptor_1.ServiceDescriptor](".nebius.applications.v1alpha1.K8sReleaseService",k8s_release_service_pb2.DESCRIPTOR,descriptor_1.ServiceDescriptor)
    __service_name__ = ".nebius.applications.v1alpha1.K8sReleaseService"
    __operation_type__ = v1_1.Operation
    __operation_service_class__ = v1_1.OperationServiceClient
    __operation_source_method__ = "Create"
    
    def get(self,
        request: "GetK8sReleaseRequest",
        metadata: abc.Iterable[builtins.tuple[builtins.str,builtins.str]]|None = None,
        timeout: builtins.float|None = None,
        credentials: grpc.CallCredentials | None = None,
        compression: grpc.Compression | None = None,
        retries: builtins.int | None = 3,
        per_retry_timeout: builtins.float | None = None,
    ) -> request_1.Request["GetK8sReleaseRequest","K8sRelease"]:
        return super().request(
            method="Get",
            request=request,
            result_pb2_class=k8s_release_pb2.K8sRelease,
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            compression=compression,
            retries=retries,
            per_retry_timeout=per_retry_timeout,
            result_wrapper=pb_classes.simple_wrapper(K8sRelease),
        )
    
    def list(self,
        request: "ListK8sReleasesRequest",
        metadata: abc.Iterable[builtins.tuple[builtins.str,builtins.str]]|None = None,
        timeout: builtins.float|None = None,
        credentials: grpc.CallCredentials | None = None,
        compression: grpc.Compression | None = None,
        retries: builtins.int | None = 3,
        per_retry_timeout: builtins.float | None = None,
    ) -> request_1.Request["ListK8sReleasesRequest","ListK8sReleasesResponse"]:
        return super().request(
            method="List",
            request=request,
            result_pb2_class=k8s_release_service_pb2.ListK8sReleasesResponse,
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            compression=compression,
            retries=retries,
            per_retry_timeout=per_retry_timeout,
            result_wrapper=pb_classes.simple_wrapper(ListK8sReleasesResponse),
        )
    
    def create(self,
        request: "CreateK8sReleaseRequest",
        metadata: abc.Iterable[builtins.tuple[builtins.str,builtins.str]]|None = None,
        timeout: builtins.float|None = None,
        credentials: grpc.CallCredentials | None = None,
        compression: grpc.Compression | None = None,
        retries: builtins.int | None = 3,
        per_retry_timeout: builtins.float | None = None,
    ) -> request_1.Request["CreateK8sReleaseRequest","operation.Operation[v1_1.Operation]"]:
        return super().request(
            method="Create",
            request=request,
            result_pb2_class=operation_pb2.Operation,
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            compression=compression,
            retries=retries,
            per_retry_timeout=per_retry_timeout,
            result_wrapper=operation.Operation,
        )
    
    def update(self,
        request: "UpdateK8sReleaseRequest",
        metadata: abc.Iterable[builtins.tuple[builtins.str,builtins.str]]|None = None,
        timeout: builtins.float|None = None,
        credentials: grpc.CallCredentials | None = None,
        compression: grpc.Compression | None = None,
        retries: builtins.int | None = 3,
        per_retry_timeout: builtins.float | None = None,
    ) -> request_1.Request["UpdateK8sReleaseRequest","operation.Operation[v1_1.Operation]"]:
        metadata = fieldmask_protobuf.ensure_reset_mask_in_metadata(request, metadata)
        return super().request(
            method="Update",
            request=request,
            result_pb2_class=operation_pb2.Operation,
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            compression=compression,
            retries=retries,
            per_retry_timeout=per_retry_timeout,
            result_wrapper=operation.Operation,
        )
    
    def delete(self,
        request: "DeleteK8sReleaseRequest",
        metadata: abc.Iterable[builtins.tuple[builtins.str,builtins.str]]|None = None,
        timeout: builtins.float|None = None,
        credentials: grpc.CallCredentials | None = None,
        compression: grpc.Compression | None = None,
        retries: builtins.int | None = 3,
        per_retry_timeout: builtins.float | None = None,
    ) -> request_1.Request["DeleteK8sReleaseRequest","operation.Operation[v1_1.Operation]"]:
        return super().request(
            method="Delete",
            request=request,
            result_pb2_class=operation_pb2.Operation,
            metadata=metadata,
            timeout=timeout,
            credentials=credentials,
            compression=compression,
            retries=retries,
            per_retry_timeout=per_retry_timeout,
            result_wrapper=operation.Operation,
        )
    

__all__ = [
    #@ local import names here @#
    "K8sRelease",
    "K8sReleaseSpec",
    "K8sReleaseStatus",
    "GetK8sReleaseRequest",
    "ListK8sReleasesRequest",
    "CreateK8sReleaseRequest",
    "UpdateK8sReleaseRequest",
    "DeleteK8sReleaseRequest",
    "ListK8sReleasesResponse",
    "K8sReleaseServiceClient",
]
