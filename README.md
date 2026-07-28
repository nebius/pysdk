# Nebius Python® SDK

The **Nebius Python® SDK** is a client library for
[Nebius AI Cloud](https://nebius.com) services. It uses gRPC and supports all
APIs in the [Nebius API repository](https://github.com/nebius/api). Use the SDK
to authenticate, manage resources, and communicate with Nebius services.

> **Note**: "Python" and the Python logos are trademarks or registered trademarks of the Python Software Foundation, used by Nebius B.V. with permission from the Foundation.

### Full documentation and reference

See the [API reference](https://nebius.github.io/pysdk/apiReference.html) for
all services and methods.

### Installation

```bash
pip install nebius
```

If you have a ZIP archive or a Git checkout, install the SDK from its directory:

```bash
pip install ./path/to/your/pysdk
```

### Migration from 0.3.x to 0.4.x

Version 0.4.0 replaces the provider-backed generated API layer. The new layer
contains SDK-owned message, enum, reflection, and service-client
implementations. Imports from public package facades and client calls continue
to work:

```python
from nebius.api.nebius.compute.v1 import Instance, InstanceServiceClient
```

The SDK no longer contains generated `*_pb2.py`, `*_pb2.pyi`, and
`*_pb2_grpc.py` modules. Change code that imported these modules directly.
Also change code that depended on `google.protobuf.message.Message` or used the
global protobuf descriptor pool. Use the package-facade exports and the SDK
registry and reflection APIs instead. The SDK now supplies its required Google
protobuf and RPC types in `nebius.api.google.protobuf` and
`nebius.api.google.rpc`.

### Migration from 0.2.x to 0.3.x

Version 0.3.0 contains these changes to authorization:

- Authorization options moved to a direct request argument.
- The SDK removed `nebius.aio.authorization.options.options_to_metadata`.
- The SDK removed unused metadata cleanup.

`<= 0.2.74`:
```python
from nebius.aio.authorization.options import options_to_metadata
service.request(
    req,
    metadata=({'your':'metadata'}).update(options_to_metadata(
        {
            OPTION_RENEW_REQUIRED: "true",
            OPTION_RENEW_SYNCHRONOUS: "true",
            OPTION_RENEW_REQUEST_TIMEOUT: ".9",
        }
    ))
)
```

`>= 0.3.0`:
```python
service.request(
    req,
    metadata={'your':'metadata'},
    auth_options={
        OPTION_RENEW_REQUIRED: "true",
        OPTION_RENEW_SYNCHRONOUS: "true",
        OPTION_RENEW_REQUEST_TIMEOUT: ".9",
    }
)
```

### Example

Working examples are in `src/nebius/examples`. From the repository root, run
an example as follows:
```bash
NEBIUS_IAM_TOKEN=$(nebius iam get-access-token) PYTHONPATH=src \
python -m nebius.examples.basic your-project-id
```

### How-to

#### Initialize

```python
from nebius.sdk import SDK

sdk = SDK(user_agent_prefix="example-application/1.0")
```

This code initializes the
[SDK](https://nebius.github.io/pysdk/nebius.sdk.SDK.html) with an IAM token
from the `NEBIUS_IAM_TOKEN` environment variable. Replace
`example-application/1.0` with the name and version of your application.

The following sections show the supported credential sources.

##### Initialize with an IAM token

You can give the token directly to the SDK. You can also read it from a
different environment variable:

```python
import os
from nebius.sdk import SDK
from nebius.aio.token.static import Bearer, EnvBearer  # [1]
from nebius.aio.token.token import Token  # [2]

sdk = SDK(
    credentials=os.environ.get("NEBIUS_IAM_TOKEN", ""),
    user_agent_prefix="example-application/1.0",
)
# or
sdk = SDK(
    credentials=Bearer(os.environ.get("NEBIUS_IAM_TOKEN", "")),
    user_agent_prefix="example-application/1.0",
)
# or
sdk = SDK(
    credentials=EnvBearer("NEBIUS_IAM_TOKEN"),
    user_agent_prefix="example-application/1.0",
)
# or
sdk = SDK(
    credentials=Bearer(Token(os.environ.get("NEBIUS_IAM_TOKEN", ""))),
    user_agent_prefix="example-application/1.0",
)
```
[[1](https://nebius.github.io/pysdk/nebius.aio.token.static.html), [2](https://nebius.github.io/pysdk/nebius.aio.token.token.html)]

Each example gets the same token through a different credential interface.

##### Initialize using CLI config

If you configured the [Nebius AI Cloud CLI](https://docs.nebius.com/cli), you
can initialize the SDK with its
[CLI configuration](https://nebius.github.io/pysdk/nebius.aio.cli_config.Config.html):

```python
from nebius.sdk import SDK
from nebius.aio.cli_config import Config

sdk = SDK(
    config_reader=Config(),
    user_agent_prefix="example-application/1.0",
)
```

The SDK also reads the domain from the configured endpoint if you do not set
the domain explicitly.

The SDK uses the token in `NEBIUS_IAM_TOKEN` if this variable is set. It uses
`NEBIUS_PROFILE` to select a profile in the same way as the CLI. Set
`Config(no_env=True)` to ignore these environment variables.

The configuration reader can also get the default parent ID:

```python
from nebius.aio.cli_config import Config

print(f"My default parent ID: {Config().parent_id}")
```

See the
[`Config` documentation](https://nebius.github.io/pysdk/nebius.aio.cli_config.Config.html)
for settings such as the file path, profile name, metrics, and environment
variable names. `Config(metrics=...)` receives configuration and authentication
callbacks. `Config(auth_metrics=...)` receives only authentication callbacks
for credentials from the configuration reader. If you attach callbacks later
with `Config.set_metrics(...)`, the reader replays the last configuration-load
event.

##### Initialize with the private key file

You can authorize with a service account and its private key. In the following
example, specify the service account ID and the public key ID for your private
key. Also change the path to your `private_key.pem` file.

```python
from nebius.sdk import SDK
from nebius.base.service_account.pk_file import Reader as PKReader  # [1]

sdk = SDK(
    credentials=PKReader(
        filename="location/of/your/private_key.pem",
        public_key_id="public-key-id",
        service_account_id="your-service-account-id",
    ),
    user_agent_prefix="example-application/1.0",
)
# or without importing PKReader
sdk = SDK(
    service_account_private_key_file_name="location/of/your/private_key.pem",
    service_account_public_key_id="public-key-id",
    service_account_id="your-service-account-id",
    user_agent_prefix="example-application/1.0",
)
```
[[1](https://nebius.github.io/pysdk/nebius.base.service_account.pk_file.Reader.html)]

##### Initialize with a credentials file

You can also use one credentials file that contains the private key and all
required IDs:

```python
from nebius.sdk import SDK
from nebius.base.service_account.credentials_file import Reader as CredentialsReader  # [1]

sdk = SDK(
    credentials=CredentialsReader(
        filename="location/of/your/credentials.json",
    ),
    user_agent_prefix="example-application/1.0",
)
# or without importing CredentialsReader
sdk = SDK(
    credentials_file_name="location/of/your/credentials.json",
    user_agent_prefix="example-application/1.0",
)
```
[[1](https://nebius.github.io/pysdk/nebius.base.service_account.credentials_file.Reader.html)]

#### Test the SDK

Use
[`SDK.whoami`](https://nebius.github.io/pysdk/nebius.sdk.SDK.html#whoami) to
test your credentials and connection. This method returns basic information
about the authenticated profile:

```python
import asyncio

async def my_call():
    async with sdk:
        print(await sdk.whoami())

asyncio.run(my_call())
```

Close the SDK to stop and collect all coroutines and tasks. Use `async with`,
as in the previous example, or call `sdk.close()` explicitly:

```python
import asyncio

async def my_call():
    try:
        print(await sdk.whoami())
        # Other calls to SDK
    finally:
        await sdk.close()

asyncio.run(my_call())
```

The SDK is designed for `asyncio`. Use an asynchronous context when possible.
If no asynchronous event loop is running, you can use the SDK synchronously:

```python
try:
    print(sdk.whoami().wait())
    # Other calls to SDK
finally:
    sdk.sync_close()
```

Synchronous calls can hang, even if you set timeouts. They do not work in an
asynchronous call stack unless the SDK has a separate event loop. A separate
loop reduces this risk but does not prevent all deadlocks.

If you do not close the SDK, unterminated tasks can cause errors.

#### Test token renewal

The SDK renews tokens when you use a service account, a credentials file, or
another renewable credential source. By default, it writes renewal errors to
the log. To receive these errors as request errors, give renewal options to the
request:


```python
import asyncio

from nebius.aio.token.renewable import (
    OPTION_RENEW_REQUEST_TIMEOUT,
    OPTION_RENEW_REQUIRED,
    OPTION_RENEW_SYNCHRONOUS,
)

async def my_call():
    try:
        await sdk.whoami(
            auth_options={
                OPTION_RENEW_REQUIRED: "true",
                OPTION_RENEW_SYNCHRONOUS: "true",
                OPTION_RENEW_REQUEST_TIMEOUT: ".9",
            }
        )
    except Exception as err:
        print(f"Token renewal failed: {err=}")
    finally:
        await sdk.close()

asyncio.run(my_call())
```

You can give these options to any request.

The `auth_timeout` value limits the total time for authentication and renewal.
The default value is 15 minutes. You can change it for one call. For example,
use `await sdk.whoami(auth_timeout=600.0)`. If you set `auth_timeout=None`,
authentication can wait indefinitely when renewal cannot finish.

#### Call a method

After you initialize and test the SDK, you can call service methods. The
following sections assume that the
[SDK](https://nebius.github.io/pysdk/nebius.sdk.SDK.html) is in the `sdk`
variable. The examples do not show how to close the SDK.

All service API classes are in submodules of `nebius.api.nebius`. See the
[API reference](https://nebius.github.io/pysdk/apiReference.html). The
`nebius.api.nebius` package also contains direct message, enum, reflection,
and service-client classes.

This example gets a bucket from Object Storage by its ID:

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

The following example makes the same call synchronously:

```python
import asyncio

from nebius.api.nebius.storage.v1 import BucketServiceClient, GetBucketRequest

service = BucketServiceClient(sdk)
result = service.get(GetBucketRequest(
    id="some-bucket-id",
)).wait()
```

##### Parent ID

Some requests contain `parent_id`. The SDK sets this field automatically in
these cases:

- The `parent_id` field is empty for the `list` and `get_by_name` methods.
- The `metadata.parent_id` field is empty for all methods except `update`.

The SDK sets `parent_id` only if initialization supplied a value. The value can
come from the
[CLI `Config`](https://nebius.github.io/pysdk/nebius.aio.cli_config.Config.html)
or the
[`SDK.parent_id`](https://nebius.github.io/pysdk/nebius.sdk.SDK.html)
attribute. To use the CLI configuration without its parent ID, set
`no_parent_id=True`.

##### Operations

Many core methods return a
[`nebius.aio.Operation`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html)
object for a long-running asynchronous operation. For example,
`BucketServiceClient.create` returns this object. The wrapper supplies methods
that monitor the operation. You can await the wrapper until the operation is
complete.

The following example uses asynchronous calls:

```python
from nebius.api.nebius.storage.v1 import BucketServiceClient, CreateBucketRequest

service = BucketServiceClient(sdk)
operation = await service.create(CreateBucketRequest(
    # Set the required fields.
))
await operation.wait()
print(f"New bucket ID: {operation.resource_id}")
```

The following example uses synchronous calls:

```python
from nebius.api.nebius.storage.v1 import BucketServiceClient, CreateBucketRequest

service = BucketServiceClient(sdk)
operation = service.create(CreateBucketRequest(
    # Set the required fields.
)).wait()
operation.wait_sync()
print(f"New bucket ID: {operation.resource_id}")
```

##### Progress tracker

Some operations supply a progress tracker with an estimated completion time,
completed-work value, and step details. Use
[`Operation.progress_tracker`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html#progress_tracker)
to get it. This method returns `None` for v1alpha1 operations and operations
without progress details.

This example polls an operation and shows progress on one line:

```python
from asyncio import sleep
from datetime import datetime
from nebius.base.protos.well_known import local_timezone

while not operation.done():
    await operation.update()
    tracker = operation.progress_tracker()
    parts = [f"waiting for operation {operation.id} to complete:"]

    if tracker:
        work = tracker.work_fraction()
        if work is not None:
            parts.append(f"{work:.0%}")

        desc = tracker.description()
        if desc:
            parts.append(desc)

        started = tracker.started_at()
        if started is not None:
            elapsed = datetime.now(local_timezone) - started
            parts.append(f"{elapsed}")

        eta = tracker.estimated_finished_at()
        if eta is not None:
            parts.append(f"eta {eta}")

    print(" ".join(parts), end="\r", flush=True)
    await sleep(1)

print()
```

##### Operations service

Use an
[`OperationServiceClient`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html)
to get or list operations.

The
[`OperationServiceClient`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html)
is in
[`nebius.api.nebius.common.v1`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.html),
but it does not work in the same way as other services. Get the applicable
operation service from the source service. Call
[`service.operation_service()`](https://nebius.github.io/pysdk/nebius.aio.client.ClientWithOperations.html#operation_service).

This asynchronous example lists operations and gets one operation:
```python
from nebius.api.nebius.common.v1 import GetOperationRequest, ListOperationsRequest
from nebius.api.nebius.storage.v1 import BucketServiceClient

service = BucketServiceClient(sdk)
op_service = service.operation_service()

resp = await op_service.list(ListOperationsRequest(resource_id="your-bucket-id"))
op_id = resp.operations[0].id  # These elements are not Operation wrappers.
real_operation = await op_service.get(GetOperationRequest(id=op_id))

# The get method returns an Operation wrapper that you can await.
await real_operation.wait()
```

> **Note:** Only
> [`get`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html#get)
> returns a complete
> [`Operation`](https://nebius.github.io/pysdk/nebius.aio.operation.Operation.html)
> wrapper. Methods such as
> [`list`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.OperationServiceClient.html#list)
> and Compute
> [`list_operations_by_parent`](https://nebius.github.io/pysdk/nebius.api.nebius.compute.v1.DiskServiceClient.html#list_operations_by_parent)
> return an internal
> [`Operation`](https://nebius.github.io/pysdk/nebius.api.nebius.common.v1.Operation.html)
> representation. You cannot await or poll this internal representation as an
> `Operation` wrapper.

##### Timeouts and retries

SDK requests have an internal retry layer and two request timeouts:

- Overall request timeout: Limits the complete request, including all retries.
- Per-retry timeout: Limits each retry attempt. If you do not set this value,
  it uses the overall request timeout.

By default, the overall request timeout is 60 seconds and the per-retry timeout
is 20 seconds (`60 / 3`). To disable timeouts for one call, set
`timeout=None`. For example, use `service.get(req, timeout=None)`. Without a
timeout, a request can wait indefinitely.

Network errors, resource exhaustion, quota errors, and service errors can stop
a retry loop. Timeouts are not the only possible cause. If an attempt can wait
on a slow resource, set a shorter per-retry timeout. The attempt then fails
sooner, and the retry loop can continue or return the error.

Operations add an operation-level timeout. This timeout limits the complete
operation lifecycle. The names of timeouts for each operation update request
have the `poll_` prefix.

###### Authentication timeout (auth_timeout)

The independent `auth_timeout` value limits the complete authentication flow.
Authentication includes token acquisition or renewal and can retry before and
during the RPC. This timeout includes internal authentication retries and the
request inside the authentication loop.

- Default: 15 minutes (900 seconds)
- Scope: The authentication loop and its request
- Behavior:
    - The credential provider controls authentication retries. For example, it
      can retry after a temporary network error or an `UNAUTHENTICATED`
      response. `auth_timeout` limits all these retries.
    - For synchronous calls such as `.wait()`, `auth_timeout` limits the total
      wait time.
- Per-call change: Give `auth_timeout` to a service method. For example:

```python
response = await service.get(req, auth_timeout=300.0)  # 5 minutes
```

- To disable the authentication deadline, set `auth_timeout=None`.
  Authentication can then wait indefinitely if it does not succeed.

Notes:

- `auth_timeout` starts with the request. It limits the authorized request
  `timeout`, which limits each `per_retry_timeout`.
- Individual token-exchange attempts can have shorter deadlines.
  `auth_timeout` limits their total time.

##### Keepalive and metrics

By default, the SDK enables gRPC keepalive settings that are compatible with
the Nebius SDK for Go. You can change them with the
`NEBIUS_GRPC_KEEPALIVE_TIME`, `NEBIUS_GRPC_KEEPALIVE_TIMEOUT`, and
`NEBIUS_GRPC_KEEPALIVE_PERMIT_WITHOUT_STREAM` environment variables. To
disable SDK keepalive, set `keepalive=False`. You can also give explicit
options:

```python
from nebius.aio.keepalive import KeepaliveOptions
from nebius.sdk import SDK

sdk = SDK(
    keepalive=KeepaliveOptions(time_ms=20_000, timeout_ms=10_000),
    user_agent_prefix="example-application/1.0",
)
```

Metrics are optional and use callbacks. Give `metrics` to `SDK` or `Config` to
receive configuration and authentication events. Give `auth_metrics` to
receive only authentication events. Callback names can use snake_case or
camelCase.

Synchronous callbacks work in all contexts. The SDK schedules asynchronous
callbacks when an event loop is running. It waits for them when synchronous
code emits an event. `callback_timeout_seconds` limits awaitable callback
results. Its default value is 1 second, and the SDK adjusts invalid values to
its limits.

This timeout uses cooperative cancellation. A callback can still block the
event loop if it ignores cancellation, blocks execution, or does not await
frequently. Keep metric callbacks fast and nonblocking.

```python
from nebius.aio.cli_config import Config
from nebius.aio.metrics import Metrics
from nebius.sdk import SDK


def config_load(metric):
    print(metric.source, metric.result, metric.duration_seconds)


def token_acquire(metric):
    print(metric.provider, metric.result, metric.attempt)


sdk = SDK(
    config_reader=Config(
        metrics=Metrics(
            config_load=config_load,
            token_acquire=token_acquire,
            callback_timeout_seconds=0.5,
        )
    ),
    user_agent_prefix="example-application/1.0",
)
```

The SDK ignores metric callback failures. Thus, instrumentation does not affect
SDK requests. The SDK emits token-lifetime metrics only for expiration
timestamps that contain time-zone information.


##### Retrieve additional metadata

You can get request information in addition to the result. This information
can help the Nebius support team investigate a problem. Service methods return
[`Request`](https://nebius.github.io/pysdk/nebius.aio.request.Request.html)
objects instead of basic coroutines. A `Request` object supplies information
about its request.

The following example gets the request ID and trace ID. Errors usually contain
these IDs, but you can also get them for a successful request:

```python
request = service.get(req)  # Do not await the request yet.

# Await these values in any order or at the same time.
response = await request
request_id = await request.request_id()
trace_id = await request.trace_id()

log.info(f"Server answered: {response}; Request ID: {request_id} and Trace ID: {trace_id}")
```

Use the synchronous methods in a synchronous context:

```python
request = service.get(req)  # Do not wait for the request yet.

# Call these methods in any order. The first call starts the request and waits.
response = request.wait()
request_id = request.request_id_sync()
trace_id = request.trace_id_sync()

log.info(f"Server answered: {response}; Request ID: {request_id} and Trace ID: {trace_id}")
```

##### Parse errors

A request can raise different exceptions. Server exceptions derive from
[`nebius.aio.service_error.RequestError`](https://nebius.github.io/pysdk/nebius.aio.service_error.RequestError.html).
This error contains the request status and available information from the
server.

Print `RequestError` to see the information as text. To get structured
information, read
[`nebius.aio.service_error.RequestStatusExtended`](https://nebius.github.io/pysdk/nebius.aio.service_error.RequestStatusExtended.html)
from `err.status`.

```python
from nebius.aio.service_error import RequestError

try:
    response = await service.get(req)
except RequestError as err:
    log.exception(f"Caught request error {err}")
```

Save the request ID and trace ID if you must contact Nebius support.

### Calling `update` methods on resources

For a resource `update` method, send one of these inputs:

- A manually constructed
  [`X-ResetMask`](https://nebius.github.io/pysdk/nebius.base.fieldmask.Mask.html).
- A complete resource specification that your code got and changed.

The following sections show both methods.

#### Sending a full specification

This example gets a bucket specification, doubles its size limit, and sends the
complete specification:

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

This operation checks the resource version. If another client changes the
resource concurrently, the server rejects one request. To omit the resource
version check, set `metadata.resource_version` to **0**:

```python
from nebius.api.nebius.storage.v1 import UpdateBucketRequest

bucket = await service.get(req)
bucket.spec.max_size_bytes *= 2  # Example of the change
bucket.metadata.resource_version = 0  # Skip the check and replace the resource.
operation = await service.update(
    UpdateBucketRequest(
        metadata=bucket.metadata,
        spec=bucket.spec,
    ),
)
```

This request **fully replaces** the bucket specification. It overwrites
changes from concurrent updates.


#### Updating with manually set `X-ResetMask`

You can replace values without first requesting the complete specification.
To set a value to its Protocol Buffers default, set `X-ResetMask` manually in
the metadata. The update does not overwrite an unset field or a default field
that is not in the mask.

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

This example resets only `max_size_bytes` and removes the bucket limit. It does
not unset or change other fields.

> **Note:** Nebius field masks have more detail than Google field masks. The
> two mask types are not compatible. See the Nebius API documentation for more
> information about masks.

> **Note:** Read the API documentation before you use manually set masks to
> change lists and maps.

### User-agent

Set `user_agent_prefix` in each SDK constructor. Use a value that identifies
your application and version, such as `example-application/1.0`. The SDK sends
this value to the server as part of the user-agent.

You can also add the `grpc.primary_user_agent` option to SDK `options` or
`address_options`. The SDK combines user-agent parts in approximately this
order. It omits parts that are not set:
```python
" ".join(
    [
        *primary_user_agents_from_options,
        *primary_user_agents_from_address_options,
        user_agent_prefix,
        pysdk_user_agent,
        grpc_user_agent,  # gRPC adds this value.
        *secondary_user_agents_from_options,
        *secondary_user_agents_from_address_options,
    ]
)
```

### Contributing

See the [contributing guidelines](CONTRIBUTING.md) to contribute.

### License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Nebius B.V.
