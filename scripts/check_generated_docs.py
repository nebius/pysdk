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
FRAMEWORK_MEMBERS = {
    "nebius.api.nebius.compute.v1.CreateFilesystemRequest.html": (
        "__init__",
        "metadata.setter",
        "__PROTO_DESCRIPTOR__",
        "__PROTO_FULL_NAME__",
        "__PY_TO_PB2__",
    ),
    "nebius.base.protos.direct.Message.html": (
        "from_json",
        "FromString",
        "get_descriptor",
        "is_credentials",
        "is_sensitive",
        "__dir__",
        "__repr__",
        "ByteSize",
        "check_presence",
        "Clear",
        "clear_extension",
        "ClearField",
        "CopyFrom",
        "FindInitializationErrors",
        "get_extension",
        "get_full_update_reset_mask",
        "get_mask",
        "has_extension",
        "HasField",
        "is_default",
        "IsInitialized",
        "MergeFrom",
        "MergeFromString",
        "ParseFromString",
        "SerializeToString",
        "set_extension",
        "set_mask",
        "to_json",
        "which_field_in_oneof",
        "WhichOneof",
        "__EXTENSION_REGISTRY__",
        "__FIELDS__",
        "__MAX_NESTING_DEPTH__",
        "__PB2_DESCRIPTOR__",
        "__PROTO_DESCRIPTOR__",
        "__PROTO_FULL_NAME__",
        "__PY_TO_PB2__",
        "__REGISTRY__",
        "Extensions",
    ),
    "nebius.api.google.protobuf.NullValue.html": (
        "get_descriptor",
        "__PB2_DESCRIPTOR__",
        "__PROTO_DESCRIPTOR__",
        "__PROTO_FULL_NAME__",
        "__REGISTRY__",
    ),
    "nebius.api.nebius.compute.v1.InstanceServiceClient.html": (
        "get_descriptor",
        "__PB2_DESCRIPTOR__",
        "__api_service_name__",
        "__operation_service_class__",
        "__operation_source_method__",
        "__operation_type__",
        "__registry__",
        "__service_name__",
    ),
}


def _local_html_links(page: Path) -> set[str]:
    links: set[str] = set()
    for part in page.read_text(encoding="utf-8").split('href="')[1:]:
        target = urlsplit(part.split('"', 1)[0])
        if not target.scheme and target.path.endswith(".html"):
            links.add(unquote(target.path))
    return links


def _check_framework_member_docs(output: Path) -> None:
    missing: list[str] = []
    undocumented: list[str] = []
    for page_name, members in FRAMEWORK_MEMBERS.items():
        text = (output / page_name).read_text(encoding="utf-8")
        rows = re.findall(r"<tr\b.*?</tr>", text, flags=re.DOTALL)
        for member in members:
            target = re.compile(rf'href="[^"]*#{re.escape(member)}"')
            matches = [row for row in rows if target.search(row)]
            qualified_name = f"{page_name.removesuffix('.html')}.{member}"
            if not matches:
                missing.append(qualified_name)
            elif all('class="undocumented"' in row for row in matches):
                undocumented.append(qualified_name)
    if missing:
        raise RuntimeError("documentation omitted framework-owned members: " + ", ".join(missing[:5]))
    if undocumented:
        raise RuntimeError("framework-owned members are undocumented: " + ", ".join(undocumented[:5]))


def validate(output: Path) -> None:
    missing = [name for name in REQUIRED_PAGES if not (output / name).is_file()]
    if missing:
        raise RuntimeError("documentation build omitted required API pages: " + ", ".join(missing))

    reference = (output / "apiReference.html").read_text(encoding="utf-8")
    if API_REFERENCE_LINK not in reference:
        raise RuntimeError("API reference omitted the representative Instance service client")

    _check_framework_member_docs(output)

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
        raise RuntimeError("documentation exposed generated annotation aliases: " + ", ".join(mangled_annotations[:5]))

    broken = sorted(
        link for page in output.glob("*.html") for link in _local_html_links(page) if not (output / link).is_file()
    )
    if broken:
        raise RuntimeError("documentation contains broken local links: " + ", ".join(broken[:5]))

    internal = sorted(
        {
            *output.glob("*_pb2*.html"),
            *output.glob("*._impl_*.html"),
            *output.glob("nebius.api._registry*.html"),
            *output.glob("nebius.api.*._registry_fragment.html"),
        },
    )
    if internal:
        raise RuntimeError(
            "documentation build exposed generated implementation pages: "
            + ", ".join(path.name for path in internal[:5]),
        )


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("docs/generated")
    validate(output)


if __name__ == "__main__":
    main()
