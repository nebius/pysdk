"""PyDoctor support for the generated API namespace packages."""

import ast
from pathlib import Path

from pydoctor.model import Documentable, Module, Package  # type: ignore[import-untyped]
from pydoctor.model import System as BaseSystem

_EXPORT_SHARDS = "_NEBIUS_EXPORT_SHARDS"


class NamespacePackageSystem(BaseSystem):  # type: ignore[misc]
    """Discover PEP 420 packages below :mod:`nebius.api`."""

    @staticmethod
    def _is_api_namespace(package: Package, path: Path) -> bool:
        parent_name = package.fullName()
        is_api_path = (parent_name == "nebius" and path.name == "api") or (
            parent_name == "nebius.api" or parent_name.startswith("nebius.api.")
        )
        return is_api_path and any(path.rglob("*.py"))

    def addPackage(  # noqa: N802, N803
        self,
        package_path: Path,
        parentPackage: Package | None = None,  # noqa: N803
    ) -> None:
        init = package_path / "__init__.py"
        if init.is_file():
            package = self.analyzeModule(
                init,
                package_path.name,
                parentPackage,
                is_package=True,
            )
        else:
            package = self.Package(self, package_path.name, parentPackage)
            package._py_string = ""
            self._addUnprocessedModule(package)

        for path in sorted(package_path.iterdir()):
            if path.is_dir():
                if (path / "__init__.py").is_file() or self._is_api_namespace(
                    package, path
                ):
                    self.addPackage(path, package)
            elif path.name != "__init__.py" and not path.name.startswith("."):
                self.addModuleFromPath(path, package)

    @staticmethod
    def _export_shards(package: Package) -> dict[str, str]:
        path = package.source_path
        if (
            path is None
            or path.name != "__init__.py"
            or path.parent.name != package.name
        ):
            return {}

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == _EXPORT_SHARDS
                for target in node.targets
            ):
                continue
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                return {}
            return {
                name: shard
                for name, shard in value.items()
                if isinstance(name, str) and isinstance(shard, str)
            }
        return {}

    def _publish_api_exports(self) -> None:
        for package in self.objectsOfType(Package):
            if not package.fullName().startswith("nebius.api."):
                continue
            for name, shard_name in self._export_shards(package).items():
                if name.startswith("_") or name in package.contents:
                    continue
                shard = package.contents.get(shard_name)
                if not isinstance(shard, Module):
                    continue
                exported = shard.contents.get(name)
                if exported is not None:
                    exported.reparent(package, name)
                    self._set_parent_module(exported, package)

    @classmethod
    def _set_parent_module(
        cls,
        documentable: Documentable,
        package: Package,
    ) -> None:
        for child in documentable.contents.values():
            child.parentMod = package
            cls._set_parent_module(child, package)

    def postProcess(self) -> None:  # noqa: N802
        super().postProcess()
        self._publish_api_exports()
