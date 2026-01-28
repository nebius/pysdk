"""Protobuf compiler entry point for generating Nebius SDK code."""

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import Any

from google.protobuf.compiler import plugin_pb2 as plugin

from .descriptors import FileSet
from .generators import generate_exports, generate_file
from .pygen import PyGenFile

# Set up a logger
log = logging.getLogger("NebiusGenerator")


def package_to_path(package: str) -> str:
    """Convert a package name to an ``__init__.py`` output path.

    :param package: Package name (dot-separated).
    :returns: File path suitable for the generator output.
    """
    return "/".join(package.split(".")) + "/__init__.py"


class KeyValueAction(argparse.Action):
    """argparse action for parsing ``key=value`` options into a dict."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        """Store a key/value pair on the argparse namespace."""
        kv_dict: dict[str, str] = getattr(namespace, self.dest, {}) or {}
        try:
            if isinstance(values, str):
                key, value = values.split("=", 1)
                kv_dict[key] = value
            else:
                raise argparse.ArgumentError(self, "Must be in the form key=value")
        except ValueError:
            raise argparse.ArgumentError(self, "Must be in the form key=value")
        setattr(namespace, self.dest, kv_dict)


def parse_options(parameter: str) -> argparse.Namespace:
    """Parses the `--md_opt` parameters using argparse."""
    parser = argparse.ArgumentParser(description="nebius generator options")
    parser.add_argument(
        "--log_level",
        type=str,
        default="WARNING",
        help="Set the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    parser.add_argument(
        "--import_substitution",
        action=KeyValueAction,
        default={},
        metavar="package.prefix=your.substitution",
        help="Specify package substitutions for importing pb2 and grpc packages.",
    )
    parser.add_argument(
        "--export_substitution",
        action=KeyValueAction,
        default={},
        metavar="package.prefix=your.substitution",
        help="Specify package substitutions for exporting, if they differ from import"
        " substitutions.",
    )
    parser.add_argument(
        "--debugger_connect",
        type=str,
        default="",
        help="connect to debugger, eg localhost:5678",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="some.package",
        help="Specify packages to skip. Can be used multiple times.",
    )

    # Split the parameter by commas and emulate command-line arguments
    args = ["--" + opt for opt in parameter.split(",") if opt]
    return parser.parse_args(args)


def main() -> None:
    """Generate Nebius SDK code from a protoc request."""
    # Read CodeGeneratorRequest from stdin
    input_data = sys.stdin.buffer.read()
    request = plugin.CodeGeneratorRequest()
    request.ParseFromString(input_data)

    options = parse_options(request.parameter)
    logging.basicConfig(
        level=options.log_level,
        stream=sys.stderr,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Prepare CodeGeneratorResponse
    response = plugin.CodeGeneratorResponse()
    response.supported_features = (
        plugin.CodeGeneratorResponse.Feature.FEATURE_PROTO3_OPTIONAL
    )

    results = dict[str, PyGenFile]()

    file_set = FileSet(
        request.proto_file,
        request.file_to_generate,
        options.import_substitution,
        options.export_substitution,
        options.skip,
    )
    lock_file = ""
    if (
        options.debugger_connect != ""
        and "nebius/compute/v1/network_interface.proto" in file_set.files_dict
    ):
        from urllib.parse import urlparse

        from filelock import FileLock  # type: ignore[unused-ignore,import-not-found]

        # Path to the lock file
        lock_file = "script.lock"

        # Create a lock object
        lock = FileLock(lock_file)

        import debugpy  # type: ignore[unused-ignore,import-not-found,import-untyped]

        parsed_url = urlparse(f"//{options.debugger_connect}", scheme="tcp")
        lock.acquire()
        debugpy.listen((parsed_url.hostname, parsed_url.port))  # type: ignore[unused-ignore]
        log.info("Waiting for debugger to attach...")
        debugpy.wait_for_client()  # type: ignore[unused-ignore]
        log.debug("Debugger attached. Continuing execution...")

    for file in file_set.files_generated:
        if file.package not in results:
            results[file.package] = PyGenFile(
                import_path=file.export_path.import_path,
                docstring=f"Auto-generated Nebius SDK package for ``{file.package}``",
            )
        results[file.package].append_used_names(list(file.collect_all_names()))

    file_set.check_names()

    for file in file_set.files_generated:
        generate_file(
            file,
            results[file.package],
        )

    for package, g in results.items():
        g.p("__all__ = [")
        with g:
            g.p("#@ local import names here @#")
    for file in file_set.files_generated:
        g = results[file.package]
        with g:
            generate_exports(
                file,
                g,
            )
    for package, g in results.items():
        g.p("]")

    for package, g in results.items():
        # Create a new file for each .proto file
        output_file = response.file.add()
        output_file.name = package_to_path(package)
        output_file.content = g.dumps()

    # Write the CodeGeneratorResponse to stdout
    sys.stdout.buffer.write(response.SerializeToString())

    if options.debugger_connect != "" and lock_file != "":
        lock.release()  # type: ignore[unused-ignore]


if __name__ == "__main__":
    main()
