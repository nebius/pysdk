import argparse
import logging
import sys

from google.protobuf.compiler import plugin_pb2 as plugin
from google.protobuf.descriptor_pb2 import FileDescriptorProto

# Set up a logger
log = logging.getLogger("NebiusGenerator")


def generate_markdown_file(file_descriptor: FileDescriptorProto) -> str:
    """Generates a Markdown representation of the proto file."""
    md_content = list[str]()
    md_content.append(f"# {file_descriptor.name}\n")
    md_content.append("## Messages\n")

    for message in file_descriptor.message_type:
        md_content.append(f"### {message.name}\n")
        md_content.append("| Field Name | Field Type | Field Number |\n")
        md_content.append("|------------|------------|--------------|\n")
        for field in message.field:
            md_content.append(f"| {field.name} | {field.type} | {field.number} |\n")
        md_content.append("\n")

    log.info(f"generated file {file_descriptor.name}")

    return "\n".join(md_content)


def parse_options(parameter: str) -> argparse.Namespace:
    """Parses the `--md_opt` parameters using argparse."""
    parser = argparse.ArgumentParser(description="nebius generator options")
    parser.add_argument(
        "--log_level",
        type=str,
        default="WARNING",
        help="Set the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Split the parameter by commas and emulate command-line arguments
    args = ["--" + opt for opt in parameter.split(",") if opt]
    return parser.parse_args(args)


def main() -> None:
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

    for proto_file in request.proto_file:
        # Generate the markdown content
        md_content = generate_markdown_file(proto_file)

        # Create a new file for each .proto file
        output_file = response.file.add()
        output_file.name = proto_file.name.replace(".proto", ".md")
        output_file.content = md_content

    # Write the CodeGeneratorResponse to stdout
    sys.stdout.buffer.write(response.SerializeToString())


if __name__ == "__main__":
    main()
