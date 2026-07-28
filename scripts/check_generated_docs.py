"""Validate that a documentation build contains the generated public API."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED_PAGES = (
    "apiReference.html",
    "moduleIndex.html",
    "nebius.api.html",
    "nebius.api.google.protobuf.Timestamp.html",
    "nebius.api.nebius.compute.v1.html",
    "nebius.api.nebius.compute.v1.Instance.html",
    "nebius.api.nebius.compute.v1.InstanceServiceClient.html",
)
API_REFERENCE_LINK = "nebius.api.nebius.compute.v1.InstanceServiceClient.html"


def _local_html_links(page: Path) -> set[str]:
    links: set[str] = set()
    for part in page.read_text(encoding="utf-8").split('href="')[1:]:
        target = urlsplit(part.split('"', 1)[0])
        if not target.scheme and target.path.endswith(".html"):
            links.add(unquote(target.path))
    return links


def validate(output: Path) -> None:
    missing = [name for name in REQUIRED_PAGES if not (output / name).is_file()]
    if missing:
        raise RuntimeError(
            "documentation build omitted required API pages: " + ", ".join(missing)
        )

    reference = (output / "apiReference.html").read_text(encoding="utf-8")
    if API_REFERENCE_LINK not in reference:
        raise RuntimeError(
            "API reference omitted the representative Instance service client"
        )

    mangled_annotations = [
        page.name
        for page in output.glob("nebius.api.*.html")
        if any(
            re.search(r"(?<![A-Za-z0-9_])(?:_Nebius|_type_)", line)
            and (
                'class="function-signature"' in line
                or 'class="class-signature"' in line
                or "<code>_Nebius" in line
                or "<code>_type_" in line
            )
            for line in page.read_text(encoding="utf-8").splitlines()
        )
    ]
    if mangled_annotations:
        raise RuntimeError(
            "documentation exposed generated annotation aliases: "
            + ", ".join(mangled_annotations[:5])
        )

    broken = sorted(
        link
        for page in output.glob("*.html")
        for link in _local_html_links(page)
        if not (output / link).is_file()
    )
    if broken:
        raise RuntimeError(
            "documentation contains broken local links: " + ", ".join(broken[:5])
        )

    internal = sorted(
        {
            *output.glob("*_pb2*.html"),
            *output.glob("*._impl_*.html"),
            *output.glob("nebius.api._registry*.html"),
            *output.glob("nebius.api.*._registry_fragment.html"),
        }
    )
    if internal:
        raise RuntimeError(
            "documentation build exposed generated implementation pages: "
            + ", ".join(path.name for path in internal[:5])
        )


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("docs/generated")
    validate(output)


if __name__ == "__main__":
    main()
