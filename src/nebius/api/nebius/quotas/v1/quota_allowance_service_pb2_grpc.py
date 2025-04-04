# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from nebius.api.nebius.quotas.v1 import quota_allowance_pb2 as nebius_dot_quotas_dot_v1_dot_quota__allowance__pb2
from nebius.api.nebius.quotas.v1 import quota_allowance_service_pb2 as nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2


class QuotaAllowanceServiceStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.List = channel.unary_unary(
                '/nebius.quotas.v1.QuotaAllowanceService/List',
                request_serializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.ListQuotaAllowancesRequest.SerializeToString,
                response_deserializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.ListQuotaAllowancesResponse.FromString,
                )
        self.Get = channel.unary_unary(
                '/nebius.quotas.v1.QuotaAllowanceService/Get',
                request_serializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.GetQuotaAllowanceRequest.SerializeToString,
                response_deserializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__pb2.QuotaAllowance.FromString,
                )
        self.GetByName = channel.unary_unary(
                '/nebius.quotas.v1.QuotaAllowanceService/GetByName',
                request_serializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.GetByNameRequest.SerializeToString,
                response_deserializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__pb2.QuotaAllowance.FromString,
                )


class QuotaAllowanceServiceServicer(object):
    """Missing associated documentation comment in .proto file."""

    def List(self, request, context):
        """Lists quotas by an ID of a Tenant or a Project.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Get(self, request, context):
        """Gets a quota by its ID.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetByName(self, request, context):
        """Gets a quota by an ID of a Tenant or a Project, its region, and name.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_QuotaAllowanceServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'List': grpc.unary_unary_rpc_method_handler(
                    servicer.List,
                    request_deserializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.ListQuotaAllowancesRequest.FromString,
                    response_serializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.ListQuotaAllowancesResponse.SerializeToString,
            ),
            'Get': grpc.unary_unary_rpc_method_handler(
                    servicer.Get,
                    request_deserializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.GetQuotaAllowanceRequest.FromString,
                    response_serializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__pb2.QuotaAllowance.SerializeToString,
            ),
            'GetByName': grpc.unary_unary_rpc_method_handler(
                    servicer.GetByName,
                    request_deserializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.GetByNameRequest.FromString,
                    response_serializer=nebius_dot_quotas_dot_v1_dot_quota__allowance__pb2.QuotaAllowance.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'nebius.quotas.v1.QuotaAllowanceService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class QuotaAllowanceService(object):
    """Missing associated documentation comment in .proto file."""

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
        return grpc.experimental.unary_unary(request, target, '/nebius.quotas.v1.QuotaAllowanceService/List',
            nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.ListQuotaAllowancesRequest.SerializeToString,
            nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.ListQuotaAllowancesResponse.FromString,
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
        return grpc.experimental.unary_unary(request, target, '/nebius.quotas.v1.QuotaAllowanceService/Get',
            nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.GetQuotaAllowanceRequest.SerializeToString,
            nebius_dot_quotas_dot_v1_dot_quota__allowance__pb2.QuotaAllowance.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def GetByName(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/nebius.quotas.v1.QuotaAllowanceService/GetByName',
            nebius_dot_quotas_dot_v1_dot_quota__allowance__service__pb2.GetByNameRequest.SerializeToString,
            nebius_dot_quotas_dot_v1_dot_quota__allowance__pb2.QuotaAllowance.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
