from nebius.aio.channel import Channel
from nebius.aio.request import Request
from nebius.api.nebius.iam.v1 import (
    GetProfileRequest,
    GetProfileResponse,
    ProfileServiceClient,
)


class SDK(Channel):
    def whoami(self) -> Request[GetProfileRequest, GetProfileResponse]:
        client = ProfileServiceClient(self)
        return client.get(GetProfileRequest())
