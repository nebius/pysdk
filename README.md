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

##### Initialize using CLI config

If you've set up [Nebius AI Cloud CLI](https://docs.nebius.com/cli), you can initialize the `SDK` using [CLI config](https://nebius.github.io/pysdk/nebius.aio.cli_config.Config.html):

```python
from nebius.sdk import SDK
from nebius.aio.cli_config import Config

sdk = SDK(config_reader=Config())
```

This will also import the domain if the endpoint parameter is in the config and the domain wasn't set explicitly.

*Keep in mind, that it will get the token from the `NEBIUS_IAM_TOKEN` environment variable if it is set, or use `NEBIUS_PROFILE` for selecting the profile, the same way CLI does. To stop that from happening, set `Config(no_env=True)`*

Config reader also helps with getting the default parent ID if necessary:

```python
from nebius.aio.cli_config import Config

print(f"My default parent ID: {Config().parent_id}")
```

Check the [`Config` documentation](https://nebius.github.io/pysdk/nebius.aio.cli_config.Config.html) for more settings like file path, profile name or environment variables names.

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
    async with sdk:
        print(await sdk.whoami())

asyncio.run(my_call)
```

It is important to close the SDK, so all the coroutines and tasks will be gracefully stopped and gathered. It can either be achieved by using `async with`, or by explicitly calling `sdk.close()`:

```python
import asyncio

async def my_call():
    try:
        print(await sdk.whoami())
        # Other calls to SDK
    finally:
        await sdk.close()

asyncio.run(my_call)
```

SDK is created with asyncio in mind, so the best way to call methods of it is to use an async context. But if you haven't started async loop, you can run it synchronously:

```python
try:
    print(sdk.whoami().wait())
    # Other calls to SDK
finally:
    sdk.sync_close()
```

*Keep in mind, that this may lead to some problems or infinite locks, even if timeouts have been added. Moreover, synchronous methods won't run inside an async call stack, if you haven't provided a dedicated separate loop for the SDK. And even when the loop is provided, there might be issues or deadlocks.*

Closing the SDK is not strictly necessary, but forgetting to add it may lead to a bunch of annoying errors of unterminated tasks.

#### Test token renewal

If you use service account, credentials file or something like that, SDK will renew your tokens under the hood. This renewal process will normally report to log if any errors occur. However it might be good to get the repored errors as request errors. In that case, pass special options to the request like so:


```python
import asyncio

from nebius.aio.authorization.options import options_to_metadata
from nebius.aio.token.renewable import (
    OPTION_RENEW_REQUEST_TIMEOUT,
    OPTION_RENEW_REQUIRED,
    OPTION_RENEW_SYNCHRONOUS,
)

async def my_call():
    try:
        await sdk.whoami(
            metadata=options_to_metadata(
                {
                    OPTION_RENEW_REQUIRED: "true",
                    OPTION_RENEW_SYNCHRONOUS: "true",
                    OPTION_RENEW_REQUEST_TIMEOUT: ".9",
                }
            )
        )
    except Exception as err:
        print(f"something is wrong with your token: {err=}")
    finally:
        await sdk.close()

asyncio.run(my_call)
```

You can pass these options to any request, or add them to your metadata with `add_options_to_metadata`.

#### Call some method

Now as you have your SDK initialized and tested, you may work with our services and call their methods with it. Here and further we assume, that the [SDK](https://nebius.github.io/pysdk/nebius.sdk.SDK.html) is initialized and is located in the `sdk` variable. We also omit closing the SDK.

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

##### Parent ID

Some methods may include `parent_id` in the requests, for certain methods this field is populated automatically:
* Methods `list` and `get_by_name` with an empty `parent_id`
* All other methods, except `update`, with an empty `metadata.parent_id`

The `parent_id` will only be set if it was preset at the initialization, either from the [CLI `Config`](https://nebius.github.io/pysdk/nebius.aio.cli_config.Config.html) or from the `parent_id` attribute from the [SDK](https://nebius.github.io/pysdk/nebius.sdk.SDK.html). You can disable it, retaining the CLI Config, if you set it up with `no_parent_id=True`.

##### Operations

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

##### Operations service

If you need to get an operation or list operations, you will need an [`OperationServiceClient`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html).

The [`OperationServiceClient`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html), despite being located in [`nebius.api.nebius.common.v1`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.html), **cannot** be used the same way as other services. The real operation service must be acquired from the source service of your operation using [`service.operation_service()`](https://nebius.github.io/pysdk/nebius.aio.client.ClientWithOperations.html#operation_service) method.

Example of listing operations and getting operation by service (only async for brevity):
```python
from nebius.api.nebius.common.v1 import GetOperationRequest, ListOperationsRequest
from nebius.api.nebius.storage.v1 import BucketServiceClient

service = BucketServiceClient(sdk)
op_service = service.operation_service()

resp = await op_service.list(ListOperationsRequest(resource_id="your-bucket-id"))
op_id = resp.operations[0].id # The elements of resp.operations are not of type Operation!
real_operation = await op_service.get(GetOperationRequest(id=op_id))

# Get returns the real operation that can be awaited.
await real_operation.wait()
```

**NOTE** As you can see from the example, only [`get`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html#get) will return a fully functional [`Operation`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html). Other methods like [`list`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html#list) or [`list_operations_by_parent`](https://nebius.github.io/pysdk/nebius.api.nebius.compute.v1.DiskServiceClient.html#list_operations_by_parent) from Compute will contain an internal [`Operation`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.Operation.html) representation object, that cannot be awaited or polled as a normal [`Operation`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html).

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

### User-agent

You can add your own user-agent parts to the user-agent sent to the server.
You can do it either by adding `grpc.primary_user_agent` option in your SDK `options` or `address_options`, or by setting `user_agent_prefix` option of the SDK. The resulting user-agents will be combined together roughly as:
```python
" ".join([
    [all option['grpc.primary_user_agent'] from options],
    [all option['grpc.primary_user_agent'] from address_options for current address],
    user_agent_prefix if set,
    pysdk user agent,
    grpc user agent,  # added by gRPC itself
    [all option['grpc.secondary_user_agent'] from options],
    [all option['grpc.secondary_user_agent'] from address_options for current address],
])
```

### Contributing

Contributions are welcome! Please refer to the [contributing guidelines](CONTRIBUTING.md) for more information.

### License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Nebius B.V.
