"""PyDoctor support for the generated API namespace packages."""

# mypy: disable-error-code=import-untyped

import ast
from inspect import Parameter, Signature
from pathlib import Path
from typing import Any, cast

from docutils.nodes import Text
from pydoctor.astbuilder import _AnnotationValueFormatter
from pydoctor.model import Attribute, Class, Documentable, Function, Module, Package
from pydoctor.model import System as BaseSystem

_EXPORT_SHARDS = "_NEBIUS_EXPORT_SHARDS"
_GENERATED_TYPE_PREFIX = "_Nebius"
_GENERATED_MODULE_PREFIX = "_type_"
_STUB_MODULE_NAME = "_pysdk_stub"


class _PublicAnnotationNames(ast.NodeTransformer):
    def __init__(
        self,
        source: Module,
        package: Package,
        public_names: dict[str, str],
        alias_targets: dict[str, str],
        rewrite_private_aliases: bool = False,
    ) -> None:
        self._source = source
        self._package = package
        self._public_names = public_names
        self._alias_targets = alias_targets
        self._rewrite_private_aliases = rewrite_private_aliases

    def _reference(self, target: str, node: ast.expr) -> ast.expr:
        for alias, public_target in self._alias_targets.items():
            if target == alias or target.startswith(alias + "."):
                target = public_target + target.removeprefix(alias)
                break
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

    def _expand(self, name: str) -> str:
        for alias in self._alias_targets:
            if alias.rsplit(".", 1)[-1] == name:
                return alias
        return cast(str, self._source.expandName(name))

    def visit_Name(self, node: ast.Name) -> ast.expr:  # noqa: N802
        expanded = self._expand(node.id)
        if expanded in self._alias_targets:
            return self._reference(expanded, node)
        prefixes = (_GENERATED_TYPE_PREFIX, _GENERATED_MODULE_PREFIX)
        if not node.id.startswith(prefixes) and not (self._rewrite_private_aliases and node.id.startswith("_")):
            return node
        return self._reference(self._source.expandName(node.id), node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.expr:  # noqa: N802
        parts: list[str] = []
        value: ast.expr = node
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            target = ".".join((self._expand(value.id), *reversed(parts)))
            if any(target == alias or target.startswith(alias + ".") for alias in self._alias_targets) or (
                value.id.startswith(_GENERATED_MODULE_PREFIX)
                or self._rewrite_private_aliases
                and value.id.startswith("_")
            ):
                return self._reference(target, node)
        return cast(ast.expr, self.generic_visit(node))


class NamespacePackageSystem(BaseSystem):  # type: ignore[misc]
    """Discover PEP 420 packages below :mod:`nebius.api`."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._pysdk_stubs: dict[Package, Module] = {}

    @staticmethod
    def _is_api_namespace(package: Package, path: Path) -> bool:
        parent_name = package.fullName()
        is_api_path = (parent_name == "nebius" and path.name == "api") or (
            parent_name == "nebius.api" or parent_name.startswith("nebius.api.")
        )
        return is_api_path and any(path.rglob("*.py"))

    def addPackage(  # noqa: N802
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

        stub = package_path / "__init__.pyi"
        if stub.is_file():
            self._pysdk_stubs[package] = self.analyzeModule(
                stub,
                _STUB_MODULE_NAME,
                package,
            )

        for path in sorted(package_path.iterdir()):
            if path.is_dir():
                if (path / "__init__.py").is_file() or self._is_api_namespace(package, path):
                    self.addPackage(path, package)
            elif path.name != "__init__.py" and not path.name.startswith("."):
                self.addModuleFromPath(path, package)

    @staticmethod
    def _export_shards(package: Package) -> dict[str, str]:
        path = package.source_path
        if path is None or path.name != "__init__.py" or path.parent.name != package.name:
            return {}

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == _EXPORT_SHARDS for target in node.targets):
                continue
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                return {}
            return {name: shard for name, shard in value.items() if isinstance(name, str) and isinstance(shard, str)}
        return {}

    def _publish_api_exports(self) -> None:
        packages = [
            package
            for package in self.objectsOfType(Package)
            if package.fullName().startswith("nebius.api.") and package not in self._pysdk_stubs
        ]
        exports_by_package = {package: self._export_shards(package) for package in packages}
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
                    target = package.fullName() + "." + target.removeprefix(shard_prefix)
                alias_targets[f"{package.fullName()}.{name}"] = target

        for package, exports in exports_by_package.items():
            public_names = {name: f"{package.fullName()}.{name}" for name in exports if not name.startswith("_")}
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
        rewrite_private_aliases: bool = False,
    ) -> None:
        transformer = _PublicAnnotationNames(
            source,
            package,
            public_names,
            alias_targets,
            rewrite_private_aliases,
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
                rewrite_private_aliases,
            )

    @staticmethod
    def _package_exports(package: Package) -> set[str]:
        path = package.source_path
        if path is None or path.name != "__init__.py":
            return set()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
                continue
            value = node.value
            if value is None:
                return set()
            try:
                exports = ast.literal_eval(value)
            except (TypeError, ValueError):
                return set()
            if isinstance(exports, (list, tuple, set)):
                return {name for name in exports if isinstance(name, str)}
        return set()

    @staticmethod
    def _merge_runtime_class(stub: Class, runtime: Class) -> None:
        if not stub.docstring and runtime.docstring:
            stub.docstring = runtime.docstring
            stub.docstring_lineno = runtime.docstring_lineno
        for name, child in list(runtime.contents.items()):
            stub_child = stub.contents.get(name)
            if stub_child is None:
                child.reparent(stub, name)
            elif not stub_child.docstring and child.docstring:
                stub_child.docstring = child.docstring
                stub_child.docstring_lineno = child.docstring_lineno

    def _discard(self, documentable: Documentable) -> None:
        parent = documentable.parent
        self._remove(documentable)
        if parent is not None:
            parent.contents.pop(documentable.name, None)

    def _publish_stub_exports(self) -> None:
        for package, stub in self._pysdk_stubs.items():
            exports = self._package_exports(package)
            if not exports:
                exports = {name for name in stub.contents if not name.startswith("_")}
            alias_targets: dict[str, str] = {}
            nested_classes: list[tuple[list[str], Class]] = []
            for name, documentable in list(stub.contents.items()):
                if not isinstance(documentable, Class) or "__" not in name:
                    continue
                path = name.split("__")
                if path[0] not in exports or any(not part for part in path):
                    continue
                alias_targets[documentable.fullName()] = package.fullName() + "." + ".".join(path)
                nested_classes.append((path, documentable))

            for path, nested in sorted(nested_classes, key=lambda item: len(item[0])):
                parent = stub.contents.get(path[0])
                for part in path[1:-1]:
                    if not isinstance(parent, Class):
                        break
                    parent = parent.contents.get(part)
                if not isinstance(parent, Class):
                    continue
                existing = parent.contents.get(path[-1])
                if existing is not None and existing is not nested:
                    self._discard(existing)
                nested.reparent(parent, path[-1])

            public_names = {name: f"{package.fullName()}.{name}" for name in exports}
            for name in sorted(exports):
                exported = stub.contents.get(name)
                if exported is None:
                    continue
                self._rewrite_annotations(
                    exported,
                    stub,
                    package,
                    public_names,
                    alias_targets,
                    rewrite_private_aliases=True,
                )
                runtime = package.contents.get(name)
                if isinstance(exported, Class) and isinstance(runtime, Class):
                    self._merge_runtime_class(exported, runtime)
                if runtime is not None:
                    self._discard(runtime)
                exported.reparent(package, name)
                self._set_parent_module(exported, package)

            self._discard(stub)
            package._localNameToFullName_map.pop(_STUB_MODULE_NAME, None)

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
                ),
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
            formatted = Parameter.empty if annotation is None else _AnnotationValueFormatter(annotation, ctx=function)
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
        self._publish_stub_exports()
        self._publish_api_exports()
