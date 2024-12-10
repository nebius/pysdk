import argparse
import ast
import logging
import sys

# Custom types for readability
PrefixMap = dict[str, str]


class Replacement:
    def __init__(
        self,
        start_line: int,
        start_col: int,
        end_line: int | None,
        end_col: int | None,
        replace_to: str,
    ) -> None:
        self.start_line = start_line
        self.start_col = start_col
        self.end_line = end_line
        self.end_col = end_col
        self.replace_to = replace_to


ReplacementPositions = dict[tuple[int, int], Replacement]


class ImportTransformer(ast.NodeVisitor):
    """
    AST visitor that collects replacement positions for imports and identifiers based
    on a prefix map.
    """

    def __init__(self, prefix_map: PrefixMap) -> None:
        self.prefix_map = prefix_map
        self.replacements: ReplacementPositions = {}

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            new_name = self._replace_prefix(alias.name)
            if new_name != alias.name:
                alias.name = new_name  # Update AST node
                replacement_code = ast.unparse(alias)  # Unparse modified node to code
                replacement = Replacement(
                    alias.lineno,
                    alias.col_offset,
                    alias.end_lineno,
                    alias.end_col_offset,
                    replacement_code,
                )
                self.replacements[(alias.lineno, alias.col_offset)] = replacement

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module:
            new_name = self._replace_prefix(node.module)
            if new_name != node.module:
                node.module = new_name  # Update AST node
                replacement_code = ast.unparse(node)  # Unparse modified node to code
                replacement = Replacement(
                    node.lineno,
                    node.col_offset,
                    node.end_lineno,
                    node.end_col_offset,
                    replacement_code,
                )
                self.replacements[(node.lineno, node.col_offset)] = replacement

    def _replace_prefix(self, name: str) -> str:
        """Replace the prefix for imported names"""
        for old_prefix, new_prefix in self.prefix_map.items():
            if name.startswith(old_prefix + ".") or name == old_prefix:
                return name.replace(old_prefix, new_prefix, 1)
        return name


def parse_prefix_map(prefix_str: list[str]) -> PrefixMap:
    prefix_map: PrefixMap = {}
    for pair in prefix_str:
        if "=" not in pair:
            raise ValueError(f"Invalid prefix format: '{pair}', expected format 'A=B'")
        old, new = pair.split("=", 1)
        prefix_map[old] = new
    return prefix_map


def apply_replacements(code: str, replacements: ReplacementPositions) -> str:
    """Apply replacements to code based on line and column positions."""
    lines = code.splitlines(keepends=True)

    for _, replacement in sorted(replacements.items(), reverse=True):
        start_line = replacement.start_line
        start_col = replacement.start_col
        end_line = replacement.end_line
        end_col = replacement.end_col
        replace_to = replacement.replace_to

        # Handle replacement logic based on line and column range
        if end_line is None or start_line == end_line:
            # If there's no end_line, or it's a single-line replacement
            line = lines[start_line - 1]  # 0-based index
            lines[start_line - 1] = line[:start_col] + replace_to + line[end_col:]
        else:
            # Multi-line replacement
            # Replace the portion on the start line
            line = lines[start_line - 1]
            lines[start_line - 1] = (
                line[:start_col] + replace_to + line[start_col + len(replace_to) :]
            )

            # Replace entire lines between start_line and end_line (exclusive)
            for i in range(start_line, end_line - 1):
                lines[i] = replace_to

            # Replace the portion on the end line
            line = lines[end_line - 1]
            lines[end_line - 1] = (
                line[:start_col] + replace_to + line[start_col + len(replace_to) :]
            )

    return "".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Modify Python file imports while preserving formatting."
    )
    parser.add_argument("--input", type=str, help="Path to the input Python file")
    parser.add_argument("--output", type=str, help="Path to the output Python file")
    parser.add_argument(
        "--prefix",
        type=str,
        nargs="+",
        required=True,
        help="Prefix mappings in format 'A=B'",
    )
    parser.add_argument(
        "--level", type=str, default="info", help="Logging level (default: info)"
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.level.upper(), None),
        stream=sys.stderr,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    prefix_map = parse_prefix_map(args.prefix)
    logging.info(f"Prefix map: {prefix_map}")

    # Read the input file
    if args.input:
        with open(args.input, "r") as f:
            code = f.read()
    else:
        code = sys.stdin.read()

    # Parse the code into an AST for analysis
    try:
        tree = ast.parse(code)
        logging.info("Parsed input file successfully.")
    except SyntaxError as e:
        logging.error(f"Syntax error in input file: {e}")
        sys.exit(1)

    # Analyze the AST for transformations
    transformer = ImportTransformer(prefix_map)
    transformer.visit(tree)

    # Apply replacements by line and column positions
    modified_code = apply_replacements(code, transformer.replacements)

    # Write the modified code to the output
    if args.output:
        with open(args.output, "w") as f:
            f.write(modified_code)
            logging.info(f"Modified code written to {args.output}.")
    else:
        print(modified_code)


if __name__ == "__main__":
    main()
