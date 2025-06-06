# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from nebius.api.nebius.common.v1 import operation_pb2 as nebius_dot_common_dot_v1_dot_operation__pb2
from nebius.api.nebius.iam.v1 import group_membership_pb2 as nebius_dot_iam_dot_v1_dot_group__membership__pb2
from nebius.api.nebius.iam.v1 import group_membership_service_pb2 as nebius_dot_iam_dot_v1_dot_group__membership__service__pb2


class GroupMembershipServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Create = channel.unary_unary(
                '/nebius.iam.v1.GroupMembershipService/Create',
                request_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.CreateGroupMembershipRequest.SerializeToString,
                response_deserializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
                )
        self.Get = channel.unary_unary(
                '/nebius.iam.v1.GroupMembershipService/Get',
                request_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.GetGroupMembershipRequest.SerializeToString,
                response_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__pb2.GroupMembership.FromString,
                )
        self.GetWithAttributes = channel.unary_unary(
                '/nebius.iam.v1.GroupMembershipService/GetWithAttributes',
                request_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.GetGroupMembershipRequest.SerializeToString,
                response_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__pb2.GroupMembershipWithAttributes.FromString,
                )
        self.Delete = channel.unary_unary(
                '/nebius.iam.v1.GroupMembershipService/Delete',
                request_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.DeleteGroupMembershipRequest.SerializeToString,
                response_deserializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
                )
        self.ListMembers = channel.unary_unary(
                '/nebius.iam.v1.GroupMembershipService/ListMembers',
                request_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsRequest.SerializeToString,
                response_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsResponse.FromString,
                )
        self.ListMembersWithAttributes = channel.unary_unary(
                '/nebius.iam.v1.GroupMembershipService/ListMembersWithAttributes',
                request_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsRequest.SerializeToString,
                response_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsWithAttributesResponse.FromString,
                )
        self.ListMemberOf = channel.unary_unary(
                '/nebius.iam.v1.GroupMembershipService/ListMemberOf',
                request_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListMemberOfRequest.SerializeToString,
                response_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListMemberOfResponse.FromString,
                )


class GroupMembershipServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def Create(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Get(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetWithAttributes(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Delete(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ListMembers(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ListMembersWithAttributes(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ListMemberOf(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_GroupMembershipServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Create': grpc.unary_unary_rpc_method_handler(
                    servicer.Create,
                    request_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.CreateGroupMembershipRequest.FromString,
                    response_serializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.SerializeToString,
            ),
            'Get': grpc.unary_unary_rpc_method_handler(
                    servicer.Get,
                    request_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.GetGroupMembershipRequest.FromString,
                    response_serializer=nebius_dot_iam_dot_v1_dot_group__membership__pb2.GroupMembership.SerializeToString,
            ),
            'GetWithAttributes': grpc.unary_unary_rpc_method_handler(
                    servicer.GetWithAttributes,
                    request_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.GetGroupMembershipRequest.FromString,
                    response_serializer=nebius_dot_iam_dot_v1_dot_group__membership__pb2.GroupMembershipWithAttributes.SerializeToString,
            ),
            'Delete': grpc.unary_unary_rpc_method_handler(
                    servicer.Delete,
                    request_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.DeleteGroupMembershipRequest.FromString,
                    response_serializer=nebius_dot_common_dot_v1_dot_operation__pb2.Operation.SerializeToString,
            ),
            'ListMembers': grpc.unary_unary_rpc_method_handler(
                    servicer.ListMembers,
                    request_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsRequest.FromString,
                    response_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsResponse.SerializeToString,
            ),
            'ListMembersWithAttributes': grpc.unary_unary_rpc_method_handler(
                    servicer.ListMembersWithAttributes,
                    request_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsRequest.FromString,
                    response_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsWithAttributesResponse.SerializeToString,
            ),
            'ListMemberOf': grpc.unary_unary_rpc_method_handler(
                    servicer.ListMemberOf,
                    request_deserializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListMemberOfRequest.FromString,
                    response_serializer=nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListMemberOfResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'nebius.iam.v1.GroupMembershipService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class GroupMembershipService(object):
    """Missing associated documentation comment in .proto file."""

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
        return grpc.experimental.unary_unary(request, target, '/nebius.iam.v1.GroupMembershipService/Create',
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.CreateGroupMembershipRequest.SerializeToString,
            nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

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
        return grpc.experimental.unary_unary(request, target, '/nebius.iam.v1.GroupMembershipService/Get',
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.GetGroupMembershipRequest.SerializeToString,
            nebius_dot_iam_dot_v1_dot_group__membership__pb2.GroupMembership.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetWithAttributes(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.iam.v1.GroupMembershipService/GetWithAttributes',
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.GetGroupMembershipRequest.SerializeToString,
            nebius_dot_iam_dot_v1_dot_group__membership__pb2.GroupMembershipWithAttributes.FromString,
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
        return grpc.experimental.unary_unary(request, target, '/nebius.iam.v1.GroupMembershipService/Delete',
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.DeleteGroupMembershipRequest.SerializeToString,
            nebius_dot_common_dot_v1_dot_operation__pb2.Operation.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def ListMembers(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.iam.v1.GroupMembershipService/ListMembers',
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsRequest.SerializeToString,
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def ListMembersWithAttributes(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.iam.v1.GroupMembershipService/ListMembersWithAttributes',
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsRequest.SerializeToString,
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListGroupMembershipsWithAttributesResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def ListMemberOf(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.iam.v1.GroupMembershipService/ListMemberOf',
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListMemberOfRequest.SerializeToString,
            nebius_dot_iam_dot_v1_dot_group__membership__service__pb2.ListMemberOfResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
