import importlib
from pathlib import Path


def test_every_generated_api_module_is_importable() -> None:
    import nebius.api.nebius

    root = Path(nebius.api.nebius.__file__).parent
    modules: list[str] = []
    for source in root.rglob("*.py"):
        relative = source.relative_to(root).with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(["nebius", "api", "nebius", *parts])
        if module:
            modules.append(module)

    for module in sorted(set(modules)):
        importlib.import_module(module)
