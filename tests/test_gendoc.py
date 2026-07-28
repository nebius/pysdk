import ast
from pathlib import Path

import pytest

NamespacePackageSystem = pytest.importorskip(
    "nebius.base.gendoc.system",
    exc_type=ModuleNotFoundError,
).NamespacePackageSystem


def test_api_namespace_packages_are_discovered(tmp_path: Path) -> None:
    root = tmp_path / "nebius"
    version = root / "api" / "service" / "v1"
    examples = root / "examples"
    version.mkdir(parents=True)
    examples.mkdir()
    (root / "__init__.py").write_text('"""SDK."""')
    (version / "__init__.py").write_text(
        '"""Generated service."""\n'
        "\n"
        "_NEBIUS_EXPORT_SHARDS = {'Request': '_impl_000'}\n"
    )
    (version / "_impl_000.py").write_text(
        "class Request:\n"
        '    """Request message."""\n'
        "\n"
        "    class Choice:\n"
        '        """Nested choice."""\n'
    )
    (examples / "example.py").write_text("EXAMPLE = True\n")

    system = NamespacePackageSystem()
    builder = system.systemBuilder(system)
    builder.addModule(root)
    builder.buildModules()

    request = system.objForFullName("nebius.api.service.v1.Request")
    choice = system.objForFullName("nebius.api.service.v1.Request.Choice")
    package = system.objForFullName("nebius.api.service.v1")

    assert request is not None
    assert choice is not None
    assert choice.parentMod is package
    assert "nebius.api.service.v1._impl_000.Request" not in system.allobjects
    assert system.objForFullName("nebius.examples") is None


def test_generated_type_aliases_are_public_in_annotations(tmp_path: Path) -> None:
    root = tmp_path / "nebius"
    version = root / "api" / "service" / "v1"
    version.mkdir(parents=True)
    (root / "__init__.py").write_text('"""SDK."""')
    (version / "__init__.py").write_text(
        "_NEBIUS_EXPORT_SHARDS = {\n"
        "    'RequestMessage': '_impl_000',\n"
        "    'ResponseMessage': '_impl_000',\n"
        "    'ServiceClient': '_impl_001',\n"
        "    '_NebiusType_service_Request_deadbeef': '_impl_000',\n"
        "    '_NebiusType_service_Response_deadbeef': '_impl_000',\n"
        "}\n"
    )
    (version / "_impl_000.py").write_text(
        "class RequestMessage:\n"
        "    pass\n"
        "_NebiusType_service_Request_deadbeef = RequestMessage\n"
        "\n"
        "class ResponseMessage:\n"
        "    pass\n"
        "_NebiusType_service_Response_deadbeef = ResponseMessage\n"
    )
    (version / "_impl_001.py").write_text(
        "import acme.common as _type_acme_common\n"
        "from typing import overload\n"
        "from nebius.aio.request import Request as _NebiusRequest\n"
        "from . import (\n"
        "    _NebiusType_service_Request_deadbeef,\n"
        "    _NebiusType_service_Response_deadbeef,\n"
        ")\n"
        "\n"
        "class ServiceClient(_NebiusRequest[\n"
        "    _NebiusType_service_Request_deadbeef,\n"
        "    _NebiusType_service_Response_deadbeef,\n"
        "]):\n"
        "    @overload\n"
        "    def call(\n"
        "        self,\n"
        "        request: _NebiusType_service_Request_deadbeef,\n"
        "        external: _type_acme_common.External,\n"
        "    ) -> _NebiusRequest[\n"
        "        _NebiusType_service_Request_deadbeef,\n"
        "        _NebiusType_service_Response_deadbeef,\n"
        "    ]:\n"
        "        ...\n"
        "\n"
        "    def call(\n"
        "        self,\n"
        "        request: _NebiusType_service_Request_deadbeef,\n"
        "        external: _type_acme_common.External,\n"
        "    ) -> _NebiusRequest[\n"
        "        _NebiusType_service_Request_deadbeef,\n"
        "        _NebiusType_service_Response_deadbeef,\n"
        "    ]:\n"
        "        pass\n"
    )

    system = NamespacePackageSystem()
    builder = system.systemBuilder(system)
    builder.addModule(root)
    builder.buildModules()

    call = system.objForFullName("nebius.api.service.v1.ServiceClient.call")
    assert call is not None
    client = call.parent
    assert ast.unparse(client.rawbases[0][1]) == (
        "Request[RequestMessage, ResponseMessage]"
    )
    assert ast.unparse(call.annotations["request"]) == "RequestMessage"
    assert ast.unparse(call.annotations["external"]) == "External"
    assert (
        ast.unparse(call.annotations["return"])
        == "Request[RequestMessage, ResponseMessage]"
    )
    signature = str(call.signature)
    assert "_Nebius" not in signature
    assert "RequestMessage" in signature
    assert "ResponseMessage" in signature
    assert len(call.overloads) == 1
