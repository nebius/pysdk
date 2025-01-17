# Nebius Python SDK

The Nebius Python SDK is a comprehensive client library for interacting with [nebius.com](https://nebius.com) services.
Built on gRPC, it supports all APIs defined in the [Nebius API repository](https://github.com/nebius/api).
This SDK simplifies resource management, authentication, and communication with Nebius services, making it a valuable tool for developers.

### Full documentation and reference

To see all the services and their methods, look into the [API reference](https://nebius.github.io/pysdk/apiReference.html).

### Installation

If you've received this module in a zip archive or checked out from git, install it as follows:

```bash
pip install ./path/to/your/pysdk
```

### Example

Working examples in `src/examples`.
Try it out as follows:
```bash
NEBIUS_IAM_TOKEN=$(nebius iam get-access-token) python -m ./path/to/your/pysdk/src/examples/basic.py your-project-id
```

### How-to

#### Initialize

```python
from nebius.sdk import SDK

sdk = SDK()
```

This will initialize the [SDK](https://nebius.github.io/pysdk/nebius.sdk.SDK.html) with IAM token from `NEBIUS_IAM_TOKEN` env var.
If you want to use different ways of authorization, see next.

See the following how-to's on how to provide your crerentials.

##### Initialize using IAM Token

You can also initialize the same token these ways:

```python
import os
from nebius.sdk import SDK
from nebius.aio.token.static import Bearer, EnvBearer  # [1]
from nebius.aio.token.token import Token  # [2]

sdk = SDK(credentials=os.environ.get("NEBIUS_IAM_TOKEN", ""))
#or
sdk = SDK(credentials=Bearer(os.environ.get("NEBIUS_IAM_TOKEN", "")))
#or
sdk = SDK(credentials=EnvBearer("NEBIUS_IAM_TOKEN"))
#or
sdk = SDK(credentials=Bearer(Token(os.environ.get("NEBIUS_IAM_TOKEN", ""))))
```
[[1](https://nebius.github.io/pysdk/nebius.aio.token.static.html), [2](https://nebius.github.io/pysdk/nebius.aio.token.token.html)]

Now, your application will get token from the local Env variable, as in the example above.

##### Initialize with the private key file

Replace in the following example IDs of your service account and the public key pair for your private key.
You need to have `private_key.pem` file on your machine.

```python
from nebius.sdk import SDK
from nebius.base.service_account.pk_file import Reader as PKReader  # [1]

sdk = SDK(
    credentials=PKReader(
        filename="location/of/your/private_key.pem",
        public_key_id="public-key-id",
        service_account_id="your-service-account-id",
    ),
)
#or without importing PKReader:
sdk = SDK(
    service_account_private_key_file_name="location/of/your/private_key.pem",
    service_account_public_key_id="public-key-id",
    service_account_id="your-service-account-id",
)
```
[[1](https://nebius.github.io/pysdk/nebius.base.service_account.pk_file.Reader.html)]

##### Initialize with credentials

Assuming you have a joint credentials file with private key and all the IDs included.

```python
from nebius.sdk import SDK
from nebius.base.service_account.credentials_file import Reader as CredentialsReader  # [1]

sdk = SDK(
    credentials=CredentialsReader(
        filename="location/of/your/credentials.json",
    ),
)
#or without importing CredentialsReader:
sdk = SDK(
    credentials_file_name="location/of/your/credentials.json",
)
```
[[1](https://nebius.github.io/pysdk/nebius.base.service_account.credentials_file.Reader.html)]

#### Test the SDK

To test the SDK, you have a convenient method [`SDK.whoami`](https://nebius.github.io/pysdk/nebius.sdk.SDK.html#whoami), that will return basic info about the profile, you've authenticated with.

SDK is created around asyncio, so the best is to call it from async context:

```python
import asyncio

async def my_call():
    print(await sdk.whoami())

asyncio.run(my_call)
```

But if you haven't started async loop, you can run it synchronously:

```python
print(sdk.whoami().wait())
```
But this may lead to problems or infinite locks, even if timeouts have been added. Moreover, sync methods won't run in async call stack, if you haven't provided a dedicated separate loop for the SDK, and even then there might be issues, eg infinite blocks.

#### Call some method

Now as you have your SDK initialized and tested, you can call services methods with it. We assume, that `sdk` is created.

All the [generated API](https://nebius.github.io/pysdk/apiReference.html) is located in `nebius.api.nebius`.

The following example tries to get a bucket from storage

```python
import asyncio

from nebius.api.nebius.storage.v1 import GetBucketRequest
from nebius.api.nebius.storage.v1 import BucketServiceClient

async def my_call():
    service = BucketServiceClient(sdk)
    return await service.get(GetBucketRequest(
        id="some-bucket-id",
    ))

asyncio.run(my_call())
```

Same thing synchronously:

```python
import asyncio

from nebius.api.nebius.storage.v1 import GetBucketRequest
from nebius.api.nebius.storage.v1 import BucketServiceClient

service = BucketServiceClient(sdk)
result = service.get(GetBucketRequest(
    id="some-bucket-id",
)).wait()
```

##### Poll operations

Some methods return [`nebius.aio.Operation`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html), which needs to be finished, for instance `Create` request from the `BucketService`. Operations can be waited till completion.

Assuming, we are already in async context:

```python
from nebius.api.nebius.storage.v1 import CreateBucketRequest

service = BucketServiceStub(sdk)
operation = await service.create(CreateBucketRequest(
    # fill-in necessary fields
))
await operation.wait()
print(f"New bucket ID: {operation.resource_id}")
```

Or synchronously:
```python
from nebius.api.nebius.storage.v1 import CreateBucketRequest

service = BucketServiceStub(sdk)
operation = service.create(CreateBucketRequest(
    # fill-in necessary fields
)).wait()
operation.wait_sync()
print(f"New bucket ID: {operation.resource_id}")
```

##### Retrieve additional metadata

Sometimes you need more than just a result, for instance if you have problems, you want to provide your request ID and trace ID to Nebius support teams.

```python
request = service.get(req)  # Note, that we don't await immediately

# all three can be awaited in any order, or simultaneously
response = await request
request_id = await request.request_id()
trace_id = await request.trace_id()

log.info(f"Server answered: {response}; Request ID: {request_id} and Trace ID: {trace_id}")
```
Or in case of synchronous:

```python
request = service.get(req)  # Note, that we don't await immediately

# all three can be called in any order, the first call will start the request
response = request.wait()
request_id = request.request_id_sync()
trace_id = request.trace_id_sync()

log.info(f"Server answered: {response}; Request ID: {request_id} and Trace ID: {trace_id}")
```

##### Parse errors

Sometimes things go wrong. There are many exceptions a request can raise, but some of them are created on a server. These exceptions will derive from [`nebius.aio.service_error.RequestError`](https://nebius.github.io/pysdk/nebius.aio.service_error.RequestError.html). This error will contain request status and additional information from the server, if there was any.

You can just print the RequestError to see all the info in readable format, or you can parse [`nebius.aio.service_error.RequestStatusExtended`](https://nebius.github.io/pysdk/nebius.aio.service_error.RequestStatusExtended.html) located in `caught_error.status`, which will contain all the information in structured form.

```python
from nebius.aio.service_error import RequestError
from nebius.base.service_error import from_error

try:
    response = await service.get(req)
except RequestError as e:
    log.exception(f"Caught request error {e}")
```

Do not forget to save request ID and trace ID from the output, in case you will submit something to support.

### Call `Update` methods

Any `Update` method requires either to pass a manually constructed [`x-resetmask`](https://nebius.github.io/pysdk/nebius.base.fieldmask.Mask.html) or to send a fully set new specification. Here are both examples:

#### Using full state modifications

```python
from nebius.api.nebius.storage.v1 import UpdateBucketRequest

bucket = await service.get(req)
bucket.spec.max_size_bytes *= 2  # Example of the change
operation = await service.update(
    UpdateBucketRequest(
        metadata=bucket.metadata,
        spec=bucket.spec,
    ),
)
```

This will double the bucket volume limit, respecting the resource version.

If during your modification (between `get` and `update`) there was another concurrent one, the request will fail. You may ommit resource version check by resetting `resource_version` to **0**:

```python
from nebius.api.nebius.storage.v1 import UpdateBucketRequest

bucket = await service.get(req)
bucket.spec.max_size_bytes *= 2  # Example of the change
bucket.metadata.resource_version = 0  # This will skip version check and fully overwrite the resource
operation = await service.update(
    UpdateBucketRequest(
        metadata=bucket.metadata,
        spec=bucket.spec,
    ),
)
```

This will fully replace the bucket specification to the sent one, overwriting any changes that could have been made by any concurrent updates.


#### Using manually set `X-ResetMask`

You may want to send partial updates without requesting full specification beforehand, this process will require manual setting of the `X-ResetMask` in the metadata. Any unset or default fields without one will not be overwritten.

```python
from nebius.api.nebius.storage.v1 import UpdateBucketRequest
from nebius.api.nebius.common.v1 import ResourceMetadata
from nebius.base.metadata import Metadata

md = Metadata()
md["X-ResetMask"] = "spec.max_size_bytes"
operation = await service.update(
    UpdateBucketRequest(
        metadata=ResourceMetadata(
            id="some-bucket-id",  # Required to identify the resource
        )
    ),
    metadata=md,
)
```
This example will only reset `max_size_bytes` in the bucket, clearing the limit, but won't unset anything else.

**Note**: Our internal field masks have more granularity than google ones, so they are incompatible. You can read more on the masks in the Nebius API documentation.

**Note**: Please read the API documentation before modifying lists and maps with manual masks.

### Contributing

Contributions are welcome! Please refer to the [contributing guidelines](CONTRIBUTING.md) for more information.

### License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2024 Nebius B.V.
