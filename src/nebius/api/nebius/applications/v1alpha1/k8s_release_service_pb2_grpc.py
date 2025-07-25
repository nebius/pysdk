# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from nebius.api.nebius.applications.v1alpha1 import k8s_release_pb2 as nebius_dot_applications_dot_v1alpha1_dot_k8s__release__pb2
from nebius.api.nebius.applications.v1alpha1 import k8s_release_service_pb2 as nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2
from nebius.api.nebius.common.v1 import operation_pb2 as nebius_dot_common_dot_v1_dot_operation__pb2


class K8sReleaseServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Get = channel.unary_unary(
                '/nebius.applications.v1alpha1.K8sReleaseService/Get',
                request_serializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.GetK8sReleaseRequest.SerializeToString,
                response_deserializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__pb2.K8sRelease.FromString,
                )
        self.List = channel.unary_unary(
                '/nebius.applications.v1alpha1.K8sReleaseService/List',
                request_serializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.ListK8sReleasesRequest.SerializeToString,
                response_deserializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.ListK8sReleasesResponse.FromString,
                )
        self.Create = channel.unary_unary(
                '/nebius.applications.v1alpha1.K8sReleaseService/Create',
                request_serializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.CreateK8sReleaseRequest.SerializeToString,
                response_deserializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
                )
        self.Update = channel.unary_unary(
                '/nebius.applications.v1alpha1.K8sReleaseService/Update',
                request_serializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.UpdateK8sReleaseRequest.SerializeToString,
                response_deserializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
                )
        self.Delete = channel.unary_unary(
                '/nebius.applications.v1alpha1.K8sReleaseService/Delete',
                request_serializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.DeleteK8sReleaseRequest.SerializeToString,
                response_deserializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
                )


class K8sReleaseServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def Get(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def List(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Create(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Update(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Delete(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_K8sReleaseServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Get': grpc.unary_unary_rpc_method_handler(
                    servicer.Get,
                    request_deserializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.GetK8sReleaseRequest.FromString,
                    response_serializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__pb2.K8sRelease.SerializeToString,
            ),
            'List': grpc.unary_unary_rpc_method_handler(
                    servicer.List,
                    request_deserializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.ListK8sReleasesRequest.FromString,
                    response_serializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.ListK8sReleasesResponse.SerializeToString,
            ),
            'Create': grpc.unary_unary_rpc_method_handler(
                    servicer.Create,
                    request_deserializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.CreateK8sReleaseRequest.FromString,
                    response_serializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.SerializeToString,
            ),
            'Update': grpc.unary_unary_rpc_method_handler(
                    servicer.Update,
                    request_deserializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.UpdateK8sReleaseRequest.FromString,
                    response_serializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.SerializeToString,
            ),
            'Delete': grpc.unary_unary_rpc_method_handler(
                    servicer.Delete,
                    request_deserializer=nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.DeleteK8sReleaseRequest.FromString,
                    response_serializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'nebius.applications.v1alpha1.K8sReleaseService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class K8sReleaseService(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def Get(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.applications.v1alpha1.K8sReleaseService/Get',
            nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.GetK8sReleaseRequest.SerializeToString,
            nebius_dot_applications_dot_v1alpha1_dot_k8s__release__pb2.K8sRelease.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def List(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.applications.v1alpha1.K8sReleaseService/List',
            nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.ListK8sReleasesRequest.SerializeToString,
            nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.ListK8sReleasesResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Create(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.applications.v1alpha1.K8sReleaseService/Create',
            nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.CreateK8sReleaseRequest.SerializeToString,
            nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Update(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.applications.v1alpha1.K8sReleaseService/Update',
            nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.UpdateK8sReleaseRequest.SerializeToString,
            nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Delete(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.applications.v1alpha1.K8sReleaseService/Delete',
            nebius_dot_applications_dot_v1alpha1_dot_k8s__release__service__pb2.DeleteK8sReleaseRequest.SerializeToString,
            nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
