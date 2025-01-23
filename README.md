# Nebius Python® SDK

The **Nebius Python® SDK** is a comprehensive client library for interacting with [nebius.com](https://nebius.com) services.
Built on gRPC, it supports all APIs defined in the [Nebius API repository](https://github.com/nebius/api).
This SDK simplifies resource management, authentication, and communication with Nebius services, making it a valuable tool for developers.

> **Note**: "Python" and the Python logos are trademarks or registered trademarks of the Python Software Foundation, used by Nebius B.V. with permission from the Foundation.

### Full documentation and reference

To see all the services and their methods, look into the [API reference](https://nebius.github.io/pysdk/apiReference.html).

### Installation

```bash
pip install nebius
```

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

This will initialize the [SDK](https://nebius.github.io/pysdk/nebius.sdk.SDK.html) with an IAM token from a `NEBIUS_IAM_TOKEN` env var.
If you want to use different ways of authorization, read further.

See the following how-to's on how to provide your crerentials:

##### Initialize using an IAM Token

You can also initialize the `SDK` by providing the token directly or from the other environment variable, here are examples how to do that:

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

Now, your application will get token from the local Env variable, as in the example above, but provided in several other ways.

##### Initialize with the private key file

If you have a private key and a service account, you may want to authorize using them. Here is an example of how to do it.

Replace in the IDs in the following example with your service account and public key ID pair, related to the private key you have.
You need to have a `private_key.pem` file on your machine, modify the file path in the example accordingly.

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

##### Initialize with a credentials file

Assuming you have a joint credentials file with a private key and all the IDs inside.

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

Now as you've initialized the SDK, you may want to test whether your credentials are ok, everything works and you have a good connection.

To test the SDK, we provide a convenient method [`SDK.whoami`](https://nebius.github.io/pysdk/nebius.sdk.SDK.html#whoami), that will return the basic information about the profile, you've authenticated with:

```python
import asyncio

async def my_call():
    print(await sdk.whoami())

asyncio.run(my_call)
```

SDK is created with asyncio in mind, so the best way to call methods of it is to use an async context. But if you haven't started async loop, you can run it synchronously:

```python
print(sdk.whoami().wait())
```

*Keep in mind, that this may lead to some problems or infinite locks, even if timeouts have been added. Moreover, synchronous methods won't run inside an async call stack, if you haven't provided a dedicated separate loop for the SDK. And even when the loop is provided, there might be issues or deadlocks.*

#### Call some method

Now as you have your SDK initialized and tested, you may work with our services and call their methods with it. Here and further we assume, that the [SDK](https://nebius.github.io/pysdk/nebius.sdk.SDK.html) is initialized and is located in the `sdk` variable.

All the services API classes are located in submodules of `nebius.api.nebius`. [The reference can be found here](https://nebius.github.io/pysdk/apiReference.html). The `nebius.api.nebius` also includes all the raw gRPC and ProtoBuf classes.

As an example how to use the API, let's receive a bucket from a storage service by its ID:

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

Same thing, but synchronously:

```python
import asyncio

from nebius.api.nebius.storage.v1 import BucketServiceClient, GetBucketRequest

service = BucketServiceClient(sdk)
result = service.get(GetBucketRequest(
    id="some-bucket-id",
)).wait()
```

##### Poll operations

Many core methods return a [`nebius.aio.Operation`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html) object, representing a time-consuming asynchronous operation. For example, the `create` request from the `BucketServiceClient` above is one of such cases. The [`nebius.aio.Operation`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html) is a wrapper class that provides convenient methods for working with operations. It can be awaited util completion.

Here is an async example:

```python
from nebius.api.nebius.storage.v1 import BucketServiceClient, CreateBucketRequest

service = BucketServiceClient(sdk)
operation = await service.create(CreateBucketRequest(
    # fill-in necessary fields
))
await operation.wait()
print(f"New bucket ID: {operation.resource_id}")
```

Or synchronously:

```python
from nebius.api.nebius.storage.v1 import BucketServiceClient, CreateBucketRequest

service = BucketServiceClient(sdk)
operation = service.create(CreateBucketRequest(
    # fill-in necessary fields
)).wait()
operation.wait_sync()
print(f"New bucket ID: {operation.resource_id}")
```

##### Retrieve additional metadata

Sometimes you need more than just a result of your request. For instance, if you have problems, you may want to provide more information about the request to the Nebius support team. Service methods do not return basic coroutines, they return [`Request`](https://nebius.github.io/pysdk/nebius.aio.request.Request.html) objects, that can provide more information about the request itself.

Here is an example how to retrieve the request ID and the trace ID for referencing. In most cases, the error will contain them already, but maybe you want to reference a successful request as well. The example:

```python
request = service.get(req)  # Note, that we don't await immediately

# all three can be awaited in any order, or simultaneously
response = await request
request_id = await request.request_id()
trace_id = await request.trace_id()

log.info(f"Server answered: {response}; Request ID: {request_id} and Trace ID: {trace_id}")
```

Or in the case of a synchronous context:

```python
request = service.get(req)  # Note, that we don't await immediately

# all three can be called in any order, the first call will start the request and wait till completion
response = request.wait()
request_id = request.request_id_sync()
trace_id = request.trace_id_sync()

log.info(f"Server answered: {response}; Request ID: {request_id} and Trace ID: {trace_id}")
```

##### Parse errors

Sometimes things go wrong. There are many `Exception`s a request can raise, but some of them are created on a server and sent back. These exceptions will derive from the [`nebius.aio.service_error.RequestError`](https://nebius.github.io/pysdk/nebius.aio.service_error.RequestError.html). This error will contain a request status and additional information from the server, if there was any.

You can simply print the `RequestError` to see all the info in a readable format, or you can parse it and retrieve the [`nebius.aio.service_error.RequestStatusExtended`](https://nebius.github.io/pysdk/nebius.aio.service_error.RequestStatusExtended.html) located in the `err.status` of the excepted error `err`. It will contain all the information in the structured form.

```python
from nebius.aio.service_error import RequestError

try:
    response = await service.get(req)
except RequestError as err:
    log.exception(f"Caught request error {err}")
```

Do not forget to save both the request ID and the trace ID from the output, in case you will have to submit something to the support.

### Calling `update` methods on resources

Any `update` method on resources requires either to pass a manually constructed [`x-resetmask`](https://nebius.github.io/pysdk/nebius.base.fieldmask.Mask.html) or to send a full resource specification, previously obtained by the corresponding `get` method and then modified by your code. Here are both examples:

#### Sending a full specification

Here is an example of doubling the limit on the bucket. In this example, we receive the specification, change it and then send it back.

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

This operation respects the resource version, thus if somebody was modifying the same resource at the same time, one of your requests will not be accepted. You may omit resource version check by resetting the `metadata.resource_version`. Simply set it to **0** and your update will be applied in any situation:

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

This will **fully replace** the bucket specification with the one you've sent, overwriting any changes that could have been made by any concurrent updates.


#### Updating with manually set `X-ResetMask`

You may want to send partial updates without requesting a full specification beforehand, if your update does not require incremental changes, but only value replacements. This process will require manual setting of the `X-ResetMask` in the metadata, if you need to set any value to its default (in terms of ProtoBuf). Any unset or default fields without the mask set, will not be overwritten.

Here is an example of resetting the limit on the bucket:

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

This example will only reset `max_size_bytes` in the bucket, clearing the limit, but won't unset or change anything else.

> **Note**: Our internal field masks have more granularity than google ones, so they are incompatible. You can read more on the masks in the Nebius API documentation.

> **Note**: Please read the API documentation before modifying lists and maps using manually set masks.

### Contributing

Contributions are welcome! Please refer to the [contributing guidelines](CONTRIBUTING.md) for more information.

### License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Nebius B.V.
