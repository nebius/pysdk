"""Generate a source tree from a captured Buf request without a huge response."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, cast

from .bootstrap import (
    include_file_descriptors,
    normalize_request,
    parse_request,
    serialize_file_descriptor,
)
from .emitter import (
    emit_package_fragment,
    emit_registry,
    emit_registry_fragments,
    link_package_fragments,
    package_source_files,
    packages,
)
from .errors import GeneratorError
from .model import Graph, Options


def _write(output: Path, name: str, content: str) -> None:
    relative = PurePosixPath(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise GeneratorError(f"generated path escapes output root: {name!r}")
    path = output.joinpath(*relative.parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content)
    temporary.replace(path)


_KINDS = ("messages", "enums", "services", "extensions")
Batch = tuple[str, tuple[str, ...]]
JSONPayload = dict[str, Any]


@dataclass(frozen=True)
class FragmentAttestation:
    path: Path
    key: str
    content_hash: str
    owner: str
    files: tuple[str, ...]


def _batches(graph: Graph) -> tuple[Batch, ...]:
    emitted = sorted(graph.emitted_files)
    if graph.options.partition == "all":
        return (("all", tuple(emitted)),)
    owners: dict[str, list[str]] = {}
    for name in emitted:
        file = graph.files[name]
        if graph.options.partition == "package":
            owner = file.package or "_unpackaged"
        else:
            owner = str(PurePosixPath(name).parent)
        owners.setdefault(owner, []).append(name)
    return tuple((owner, tuple(owners[owner])) for owner in sorted(owners))


def _chunked(values: Iterable[Batch], size: int) -> Iterator[tuple[Batch, ...]]:
    iterator = iter(values)
    while batch := tuple(islice(iterator, size)):
        yield batch


def _semantic_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _symbols(graph: Graph, files: set[str]) -> dict[str, list[str]]:
    return {
        "messages": sorted(
            item.full_name
            for item in graph.messages.values()
            if item.source_file in files
        ),
        "enums": sorted(
            item.full_name for item in graph.enums.values() if item.source_file in files
        ),
        "services": sorted(
            item.full_name
            for item in graph.services.values()
            if item.source_file in files
        ),
        "extensions": sorted(
            item.full_name
            for item in graph.extensions.values()
            if item.source_file in files
        ),
    }


def _fragment_key(
    graph: Graph,
    owner: str,
    file_names: tuple[str, ...],
    semantic: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(semantic.encode())
    digest.update(graph.options.package_prefix.encode())
    digest.update(graph.options.runtime_package.encode())
    digest.update(owner.encode())
    for name in file_names:
        digest.update(name.encode())
        digest.update(serialize_file_descriptor(graph.files[name]))
        digest.update(
            graph.files[name].source_code_info.SerializeToString(deterministic=True)
        )
    for name, message_model in sorted(graph.messages.items()):
        digest.update(name.encode())
        digest.update(message_model.proto.SerializeToString(deterministic=True))
    for name, enum_model in sorted(graph.enums.items()):
        digest.update(name.encode())
        digest.update(enum_model.proto.SerializeToString(deterministic=True))
    return digest.hexdigest()


def _content_hash(payload: JSONPayload) -> str:
    content = {
        key: value
        for key, value in payload.items()
        if key not in {"invocation", "content_hash"}
    }
    serialized = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


def _cache_signing_key() -> bytes:
    configured = os.environ.get("NEBIUS_GENERATOR_CACHE_KEY_FILE")
    if configured:
        path = Path(configured).expanduser().resolve()
    else:
        state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        path = state / "nebius-generator" / "cache.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        key = secrets.token_bytes(32)
        with tempfile.NamedTemporaryFile(
            "wb",
            prefix=".cache-key.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as output:
            temporary = Path(output.name)
            os.chmod(temporary, 0o600)
            output.write(key)
            output.flush()
            os.fsync(output.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        finally:
            temporary.unlink(missing_ok=True)
    key = path.read_bytes()
    if len(key) != 32:
        raise GeneratorError(f"invalid cache signing key: {path}")
    return key


def _cache_signature(key: bytes, semantic_key: str, content_hash: str) -> str:
    message = f"{semantic_key}:{content_hash}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _analyze_files(
    graph: Graph, file_names: tuple[str, ...]
) -> dict[str, dict[str, str]]:
    source_packages = {
        source_file: package
        for package in packages(graph)
        for source_file in package_source_files(package, graph)
    }
    return {
        source_file: {
            source_packages[source_file]: emit_package_fragment(
                source_packages[source_file], source_file, graph
            )
        }
        for source_file in file_names
    }


def _analyze_batch(
    batch: Batch,
    graph: Graph,
    invocation: str,
    semantic: str,
    fragments: Path,
    cache: Path | None,
) -> FragmentAttestation:
    owner, file_names = batch
    key = _fragment_key(graph, owner, file_names, semantic)
    cache_entry = None if cache is None else cache / key
    pointer = None if cache_entry is None else cache_entry / "current"
    signing_key = None if cache is None else _cache_signing_key()
    expected_content_hash = None
    pointer_valid = False
    if pointer is not None and pointer.is_file():
        try:
            pointer_value = json.loads(pointer.read_text())
            expected_content_hash = pointer_value["content_hash"]
            if not isinstance(expected_content_hash, str):
                raise TypeError("cache content hash is not a string")
            if signing_key is None:
                raise TypeError("cache signing key is missing")
            expected_signature = _cache_signature(
                signing_key, key, expected_content_hash
            )
            pointer_valid = hmac.compare_digest(
                pointer_value["signature"], expected_signature
            )
        except (KeyError, OSError, TypeError, ValueError):
            pointer_valid = False
    cache_path = (
        None
        if cache_entry is None or expected_content_hash is None or not pointer_valid
        else cache_entry / f"{expected_content_hash}.json"
    )
    if cache_path is not None and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text())
            content_hash = _content_hash(cached)
            valid = (
                cached.get("key") == key
                and cached.get("owner") == owner
                and tuple(cached.get("files", ())) == file_names
                and cached.get("content_hash") == content_hash
                and cache_path.stem == content_hash
                and expected_content_hash == content_hash
            )
        except (OSError, ValueError, TypeError):
            valid = False
        if valid:
            cached["invocation"] = invocation
            path = fragments / f"{key}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(cached, sort_keys=True, separators=(",", ":")) + "\n"
            )
            temporary.replace(path)
            return FragmentAttestation(path, key, content_hash, owner, file_names)
    if pointer is not None:
        pointer.unlink(missing_ok=True)
    ir = _analyze_files(graph, file_names)
    payload = {
        "version": 1,
        "invocation": invocation,
        "key": key,
        "owner": owner,
        "files": list(file_names),
        "symbols": _symbols(graph, set(file_names)),
        "ir": ir,
    }
    payload["content_hash"] = _content_hash(payload)
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    if cache_entry is not None:
        if signing_key is None:
            raise GeneratorError("cache signing key is missing")
        cache_entry.mkdir(parents=True, exist_ok=True)
        cached = dict(payload)
        cached.pop("invocation")
        cached["content_hash"] = _content_hash(cached)
        cache_path = cache_entry / f"{cached['content_hash']}.json"
        with tempfile.NamedTemporaryFile(
            "w",
            prefix=f".{key}.{os.getpid()}.",
            suffix=".tmp",
            dir=cache_entry,
            delete=False,
        ) as handle:
            cache_temporary = Path(handle.name)
            handle.write(
                json.dumps(cached, sort_keys=True, separators=(",", ":")) + "\n"
            )
        os.replace(cache_temporary, cache_path)
        pointer_temporary = cache_entry / f".current.{os.getpid()}.{id(payload)}.tmp"
        pointer_value = {
            "content_hash": cached["content_hash"],
            "signature": _cache_signature(signing_key, key, cached["content_hash"]),
        }
        pointer_temporary.write_text(
            json.dumps(pointer_value, sort_keys=True, separators=(",", ":")) + "\n"
        )
        os.replace(pointer_temporary, cache_entry / "current")
    path = fragments / f"{key}.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content)
    temporary.replace(path)
    return FragmentAttestation(
        path, key, cast(str, payload["content_hash"]), owner, file_names
    )


def _verify_fragments(
    attestations: Iterable[FragmentAttestation],
    graph: Graph,
    invocation: str,
    semantic: str,
    batches: tuple[Batch, ...],
) -> dict[str, list[tuple[Path, str, str]]]:
    expected_batches = dict(batches)
    seen_owners: set[str] = set()
    actual_symbols: dict[str, list[str]] = {kind: [] for kind in _KINDS}
    package_index: dict[str, list[tuple[Path, str, str]]] = {
        package: [] for package in packages(graph)
    }
    for attestation in attestations:
        path = attestation.path
        payload = json.loads(path.read_text())
        if payload.get("version") != 1 or payload.get("invocation") != invocation:
            raise GeneratorError(f"stale or invalid fragment: {path}")
        owner = payload.get("owner")
        file_names = tuple(payload.get("files", ()))
        if (
            attestation.key != payload.get("key")
            or attestation.content_hash != payload.get("content_hash")
            or attestation.owner != owner
            or attestation.files != file_names
        ):
            raise GeneratorError(f"fragment attestation mismatch: {path}")
        if (
            owner not in expected_batches
            or owner in seen_owners
            or file_names != expected_batches[owner]
        ):
            raise GeneratorError(f"fragment ownership mismatch: {path}")
        seen_owners.add(owner)
        ir = payload.get("ir")
        if not isinstance(ir, dict) or set(ir) != set(file_names):
            raise GeneratorError(f"fragment IR ownership mismatch: {path}")
        for source_file, outputs in ir.items():
            expected_package = graph.files[source_file].package
            if not isinstance(outputs, dict) or set(outputs) != {expected_package}:
                raise GeneratorError(f"fragment IR package mismatch: {path}")
            if not isinstance(outputs[expected_package], str):
                raise GeneratorError(f"fragment IR content is invalid: {path}")
            package_index[expected_package].append(
                (path, source_file, attestation.content_hash)
            )
        batch_graph = graph.batch_view(frozenset(file_names))
        key = _fragment_key(batch_graph, owner, file_names, semantic)
        if path.stem != key or payload.get("key") != key:
            raise GeneratorError(f"fragment key mismatch: {path}")
        if payload.get("content_hash") != _content_hash(payload):
            raise GeneratorError(f"fragment content hash mismatch: {path}")
        expected_fragment_symbols = _symbols(graph, set(file_names))
        for kind in _KINDS:
            values = payload["symbols"][kind]
            if values != expected_fragment_symbols[kind]:
                raise GeneratorError(f"fragment {kind} ownership mismatch: {path}")
            actual_symbols[kind].extend(values)
    if seen_owners != set(expected_batches):
        raise GeneratorError("fragment owner coverage is incomplete")
    expected_symbols = {
        "messages": sorted(graph.messages),
        "enums": sorted(graph.enums),
        "services": sorted(graph.services),
        "extensions": sorted(graph.extensions),
    }
    for kind in _KINDS:
        values = actual_symbols[kind]
        if sorted(values) != expected_symbols[kind] or len(values) != len(set(values)):
            raise GeneratorError(
                f"fragment {kind} coverage is incomplete or duplicated"
            )
    return package_index


def _load_attested_payload(path: Path, content_hash: str) -> JSONPayload:
    payload = cast(JSONPayload, json.loads(path.read_text()))
    if (
        payload.get("content_hash") != content_hash
        or _content_hash(payload) != content_hash
    ):
        raise GeneratorError(f"fragment changed after verification: {path}")
    return payload


def generate(
    manifest: Path, output: Path, *, include_generator_protocol: bool = False
) -> None:
    raw = manifest.read_bytes()
    request = parse_request(raw)
    if include_generator_protocol:
        include_file_descriptors(request, ("google/protobuf/compiler/plugin.proto",))
    request = normalize_request(request)
    graph = Graph(request, Options.parse(request.parameter))
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    fragments = output.parent / "fragments"
    shutil.rmtree(fragments, ignore_errors=True)
    fragments.mkdir(parents=True)
    invocation = hashlib.sha256(raw).hexdigest()
    semantic = _semantic_digest()
    cache = (
        None
        if graph.options.cache_dir is None
        else Path(graph.options.cache_dir).expanduser().resolve()
    )
    batches = _batches(graph)
    attestations: list[FragmentAttestation] = []
    with ThreadPoolExecutor(max_workers=graph.options.jobs) as executor:
        for window in _chunked(batches, graph.options.jobs):
            futures = [
                executor.submit(
                    _analyze_batch,
                    batch,
                    graph.batch_view(frozenset(batch[1])),
                    invocation,
                    semantic,
                    fragments,
                    cache,
                )
                for batch in window
            ]
            for future in futures:
                attestations.append(future.result())
    package_index = _verify_fragments(
        attestations, graph, invocation, semantic, batches
    )
    registry = emit_registry(graph)
    _write(output, registry.name, registry.content)
    for fragment in emit_registry_fragments(graph):
        _write(output, fragment.name, fragment.content)
    for package in packages(graph):
        package_fragments: list[tuple[str, str]] = []
        payload_cache: dict[Path, JSONPayload] = {}
        for path, source_file, content_hash in package_index[package]:
            payload = payload_cache.get(path)
            if payload is None:
                payload = _load_attested_payload(path, content_hash)
                payload_cache[path] = payload
            package_fragments.append((source_file, payload["ir"][source_file][package]))
        for generated in link_package_fragments(package, package_fragments, graph):
            _write(output, generated.name, generated.content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--include-generator-protocol", action="store_true")
    args = parser.parse_args()
    generate(
        args.manifest,
        args.output,
        include_generator_protocol=args.include_generator_protocol,
    )


if __name__ == "__main__":
    main()
