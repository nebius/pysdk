Nebius Python SDK
=================

Working example in `src/nebius/sdk.py`.
Try it out as follows:
```bash
NEBIUS_IAM_TOKEN=$(nebius iam get-access-token) PROJECT_ID="your-project-id" python -m src/nebius/sdk.py
```

**Important note:**
Currently the classes directly use compiled grpc and proto objects. In the future, we will introduce our own wrappers that will implement all the necessary functionality and adhere to our guidelines. The future version **will** break code written with the current one.

Issues and TODOs:

 * Type wrappers
 * Unify mypy configs (different results in tox and hooks → a lot of `unused-ignore`)
 * Fieldmasks
 * Update
 * ServiceErrors
 * Synchronous functions
