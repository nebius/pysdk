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
