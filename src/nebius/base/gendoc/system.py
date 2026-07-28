"""PyDoctor support for the generated API namespace packages."""

import ast
from inspect import Parameter, Signature
from pathlib import Path
from typing import cast

from docutils.nodes import Text  # type: ignore[import-untyped]
from pydoctor.astbuilder import (  # type: ignore[import-untyped]
    _AnnotationValueFormatter,
)
from pydoctor.model import (  # type: ignore[import-untyped]
    Attribute,
    Class,
    Documentable,
    Function,
    Module,
    Package,
)
from pydoctor.model import System as BaseSystem

_EXPORT_SHARDS = "_NEBIUS_EXPORT_SHARDS"
_GENERATED_TYPE_PREFIX = "_Nebius"
_GENERATED_MODULE_PREFIX = "_type_"


class _PublicAnnotationNames(ast.NodeTransformer):
    def __init__(
        self,
        source: Module,
        package: Package,
        public_names: dict[str, str],
        alias_targets: dict[str, str],
    ) -> None:
        self._source = source
        self._package = package
        self._public_names = public_names
        self._alias_targets = alias_targets

    def _reference(self, target: str, node: ast.expr) -> ast.expr:
        target = self._alias_targets.get(target, target)
        package_prefix = self._package.fullName() + "."
        if target.startswith(package_prefix):
            relative = target.removeprefix(package_prefix)
            if relative.startswith("_impl_") and "." in relative:
                target = package_prefix + relative.split(".", 1)[1]

        if target.startswith("builtins."):
            return ast.copy_location(ast.Name(target.rsplit(".", 1)[-1]), node)

        short_name = target.rsplit(".", 1)[-1]
        existing = self._public_names.get(short_name)
        if existing is None or existing == target:
            self._public_names[short_name] = target
            self._package._localNameToFullName_map[short_name] = target
            return ast.copy_location(ast.Name(short_name), node)

        expression = ast.parse(target, mode="eval").body
        return ast.copy_location(expression, node)

    def visit_Name(self, node: ast.Name) -> ast.expr:  # noqa: N802
        if not node.id.startswith((_GENERATED_TYPE_PREFIX, _GENERATED_MODULE_PREFIX)):
            return node
        return self._reference(self._source.expandName(node.id), node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.expr:  # noqa: N802
        parts: list[str] = []
        value: ast.expr = node
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name) and value.id.startswith(
            _GENERATED_MODULE_PREFIX
        ):
            target = ".".join((self._source.expandName(value.id), *reversed(parts)))
            return self._reference(target, node)
        return cast(ast.expr, self.generic_visit(node))


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
        packages = [
            package
            for package in self.objectsOfType(Package)
            if package.fullName().startswith("nebius.api.")
        ]
        exports_by_package = {
            package: self._export_shards(package) for package in packages
        }
        alias_targets: dict[str, str] = {}
        for package, exports in exports_by_package.items():
            for name, shard_name in exports.items():
                if not name.startswith(_GENERATED_TYPE_PREFIX):
                    continue
                shard = package.contents.get(shard_name)
                if not isinstance(shard, Module):
                    continue
                target = shard.expandName(name)
                shard_prefix = shard.fullName() + "."
                if target.startswith(shard_prefix):
                    target = (
                        package.fullName() + "." + target.removeprefix(shard_prefix)
                    )
                alias_targets[f"{package.fullName()}.{name}"] = target

        for package, exports in exports_by_package.items():
            public_names = {
                name: f"{package.fullName()}.{name}"
                for name in exports
                if not name.startswith("_")
            }
            for name, shard_name in exports.items():
                if name.startswith("_") or name in package.contents:
                    continue
                shard = package.contents.get(shard_name)
                if not isinstance(shard, Module):
                    continue
                exported = shard.contents.get(name)
                if exported is not None:
                    self._rewrite_annotations(
                        exported,
                        shard,
                        package,
                        public_names,
                        alias_targets,
                    )
                    exported.reparent(package, name)
                    self._set_parent_module(exported, package)

    @classmethod
    def _rewrite_annotations(
        cls,
        documentable: Documentable,
        source: Module,
        package: Package,
        public_names: dict[str, str],
        alias_targets: dict[str, str],
    ) -> None:
        transformer = _PublicAnnotationNames(
            source,
            package,
            public_names,
            alias_targets,
        )
        if isinstance(documentable, Function):
            cls._rewrite_function_annotations(documentable, transformer)
            for overload in documentable.overloads:
                overload.signature = cls._rewrite_overload_signature(
                    overload.signature,
                    documentable,
                    transformer,
                )
        elif isinstance(documentable, Class):
            public_bases: list[tuple[str, ast.expr]] = []
            for _, base in documentable.rawbases:
                public_base = cast(ast.expr, transformer.visit(base))
                public_bases.append((ast.unparse(public_base), public_base))
            documentable.rawbases = public_bases
        elif isinstance(documentable, Attribute):
            if documentable.annotation is not None:
                documentable.annotation = transformer.visit(documentable.annotation)

        for child in documentable.contents.values():
            cls._rewrite_annotations(
                child,
                source,
                package,
                public_names,
                alias_targets,
            )

    @classmethod
    def _rewrite_function_annotations(
        cls,
        function: Function,
        transformer: _PublicAnnotationNames,
    ) -> None:
        function.annotations = {
            name: transformer.visit(annotation) if annotation is not None else None
            for name, annotation in function.annotations.items()
        }
        function.signature = cls._rewrite_signature(function.signature, function)

    @classmethod
    def _rewrite_overload_signature(
        cls,
        signature: Signature,
        function: Function,
        transformer: _PublicAnnotationNames,
    ) -> Signature:
        parameters = [
            parameter.replace(
                annotation=cls._rewrite_formatted_annotation(
                    parameter.annotation,
                    function,
                    transformer,
                )
            )
            for parameter in signature.parameters.values()
        ]
        return signature.replace(
            parameters=parameters,
            return_annotation=cls._rewrite_formatted_annotation(
                signature.return_annotation,
                function,
                transformer,
            ),
        )

    @staticmethod
    def _rewrite_formatted_annotation(
        annotation: object,
        function: Function,
        transformer: _PublicAnnotationNames,
    ) -> object:
        if not isinstance(annotation, _AnnotationValueFormatter):
            return annotation

        document = annotation._colorized.to_node()
        source = "".join(str(node) for node in document.findall(Text))
        expression = ast.parse(source, mode="eval").body
        public_expression = cast(ast.expr, transformer.visit(expression))
        return _AnnotationValueFormatter(public_expression, ctx=function)

    @staticmethod
    def _rewrite_signature(
        signature: Signature | None,
        function: Function,
    ) -> Signature | None:
        if signature is None:
            return None

        parameters = []
        for parameter in signature.parameters.values():
            annotation = function.annotations.get(parameter.name)
            formatted = (
                Parameter.empty
                if annotation is None
                else _AnnotationValueFormatter(annotation, ctx=function)
            )
            parameters.append(parameter.replace(annotation=formatted))

        return_annotation = function.annotations.get("return")
        formatted_return = (
            Parameter.empty
            if return_annotation is None
            or isinstance(return_annotation, ast.Constant)
            and return_annotation.value is None
            else _AnnotationValueFormatter(return_annotation, ctx=function)
        )
        return signature.replace(
            parameters=parameters,
            return_annotation=formatted_return,
        )

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
