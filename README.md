Nebius Python SDK
=================

**Important note:**
Currently the classes directly use compiled grpc and proto objects. In the future, we will introduce our own wrappers that will implement all the necessary functionality and adhere to our guidelines. The future version **will** break code written with the current one.

Issues and TODOs:

 * Type wrappers not implemented (no type hinting and validation)
 * Fieldmasks not implemented (Update requests have to be manually filled)
 * Synchronous functions

### Installation

If you've received this module in a zip archive or checked out from git, install it as follows:

```bash
pip install ./path/to/your/pysdk
```

### Example

Working example in `src/nebius/sdk.py`.
Try it out as follows:
```bash
NEBIUS_IAM_TOKEN=$(nebius iam get-access-token) PROJECT_ID="your-project-id" python -m ./path/to/your/pysdk/src/nebius/sdk.py
```

### How-to

#### Initialize

```python
from nebius.aio.channel import Channel

channel = Channel()
```

This will initialize the basic channel for the SDK, however you won't be able to use it unless you are authenticated.

See the following how-to's on how to provide your crerentials.

##### Initialize using IAM Token

```python
from nebius.aio.channel import Channel
from nebius.aio.token.static import Bearer
from nebius.aio.token.token import Token

channel = Channel(
    credentials=Bearer(
        Token(
            os.environ.get("NEBIUS_IAM_TOKEN", ""),
        )
    ),
)
```

Now, your application will get token from the local Env variable, as in the example above.

##### Initialize with the private key file

Replace in the following example IDs of your service account and the public key pair for your private key.
You need to have `private_key.pem` file on your machine.

```python
from nebius.aio.channel import Channel
from nebius.base.service_account.pk_file import Reader as PKReader

channel = Channel(
    credentials=PKReader(
        filename="location/of/your/private_key.pem",
        public_key_id="public-key-id",
        service_account_id="your-service-account-id",
    ),
)
```

##### Initialize with credentials

Assuming you have a joint credentials file with private key and all the IDs included.

```python
from nebius.aio.channel import Channel
from nebius.base.service_account.credentials_file import Reader as CredentialsReader

channel = Channel(
    credentials=CredentialsReader(
        filename="location/of/your/credentials.json",
    ),
)
```

#### Call some method

Now as you have your channel, you can call services methods with it. We assume, that `channel` is created.

In the current version, you have to directly use grpc generated classes. This behavior will be changed in the future, but here is the current flow.

All the generated API is located in `nebius.api.nebius`.

The following example tries to get a bucket from storage

```python
import asyncio

from nebius.api.nebius.storage.v1.bucket_service_pb2 import GetBucketRequest
from nebius.api.nebius.storage.v1.bucket_service_pb2_grpc import BucketServiceStub

async def my_call():
    service = BucketServiceStub(channel)
    req = GetBucketRequest(
        id="some-bucket-id",
    )
    return await service.Get(req)

asyncio.run(my_call)
```

##### Poll operations

Some methods return `common.*.Operation`, which needs to be finished, for instance `Create` request from the `BucketService`.

For polling operations, you have to get operation service associated with the service you're using, with `channel.get_corresponding_operation_service(YourServiceStub)`.

Assuming, we are already in async context:

```python
from nebius.api.nebius.common.v1.operation_service_pb2 import GetOperationRequest
from nebius.api.nebius.storage.v1.bucket_service_pb2 import CreateBucketRequest

service = BucketServiceStub(channel)
op_service = channel.get_corresponding_operation_service(BucketServiceStub)
operation = await service.Create(CreateBucketRequest(
    # fill-in necessary fields
))
while not operation.HasField("status"):
    await sleep(1)  # TODO: add deadline checks
    operation = await op_service.Get(GetOperationRequest(
        id=operation.id
    ))
```

##### Retrieve additional metadata

Sometimes you need more than just a result, for instance if you have problems, you want to provide your request ID and trace ID to Nebius support teams.

```python
call = service.Get(req)  # Note, that we don't await immediately
response = await call
md = await call.initial_metadata()
request_id = md["x-request-id"]
trace_id = md["x-trace-id"]
log.info(f"Server answered: {response}; Request ID: {request_id} and Trace ID: {trace_id}")
```

We advise to wrap all grpc calls with this and log these IDs.
Be careful not to log sensitive info, at this point we don't mask it.

##### Parse errors

Some errors from the services may contain additional information in the form of `common.v1.ServiceError`. To access this information, use `nebius.base.service_error.from_error`:

```python
from grpc import RpcError
from nebius.base.service_error import from_error

try:
    response = await service.Get(req)
except RpcError as e:
    service_errors = from_error(e)
    md = await e.initial_metadata()
    request_id = md["x-request-id"]
    trace_id = md["x-trace-id"]
    log.exception(f"Caught RPC error {e} with additional information {service_errors}; Request ID: {request_id} and Trace ID: {trace_id}")
```

Do not forget to log request ID and trace ID alongside.

### Call `Update` methods

`Update` methods require `ResetMask` masks to be passed alongside the request, if you want to set some fields to default. Currently, there's no python library to support Nebius `ResetMask`, so you have to create the masks yourself.

```python
from nebius.api.nebius.storage.v1.bucket_service_pb2 import UpdateBucketRequest

operation = await service.Update(
    UpdateBucketRequest(), # if we send it without metadata, it won't update anything
    metadata=[
        ("x-reset-mask","spec.max_size_bytes")  # we reset max_size_bytes to 0 — unlimited
        ("x-reset-mask","spec.versioning_policy")  # you can add multiple masks, they will be combined
    ]
)
```

**Note**: Our internal field masks have more granularity than google ones, so they are incompatible.
