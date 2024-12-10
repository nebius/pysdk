import os
import subprocess
import sys
import tempfile

# Define the path to the mover script
MOVER_SCRIPT_PATH = "./src/nebius/base/protos/compiler/mover.py"


def run_mover(
    input_code: str, prefix_args: list[str]
) -> tuple[subprocess.CompletedProcess[str], str]:
    """
    Helper function to run the mover script with given input code and prefix arguments
    """
    with (
        tempfile.NamedTemporaryFile(delete=False, suffix=".py") as input_file,
        tempfile.NamedTemporaryFile(delete=False, suffix=".py") as output_file,
    ):
        input_file.write(input_code.encode("utf-8"))
        input_file.flush()

        # Run the mover script as a subprocess
        result = subprocess.run(
            [
                sys.executable,
                MOVER_SCRIPT_PATH,
                "--input",
                input_file.name,
                "--output",
                output_file.name,
                "--prefix",
            ]
            + prefix_args,
            capture_output=True,
            text=True,
        )

        # Read output
        with open(output_file.name, "r") as f:
            output_code = f.read()

    # Cleanup temporary files
    os.remove(input_file.name)
    os.remove(output_file.name)

    return result, output_code


def test_simple_import() -> None:
    """Test simple import transformation"""
    input_code = "import A.foo.bar"
    expected_output = "import B.foo.bar"

    result, output_code = run_mover(input_code, ["A=B"])

    assert result.returncode == 0
    assert output_code == expected_output


def test_inner_import() -> None:
    """Test inner import transformation"""
    input_code = "import A.foo.bar"
    expected_output = "import B.baz.bar"

    result, output_code = run_mover(input_code, ["A.foo=B.baz"])

    assert result.returncode == 0
    assert output_code == expected_output


def test_from_import() -> None:
    """Test 'from ... import ...' transformation"""
    input_code = "from A.foo import bar"
    expected_output = "from B.foo import bar"

    result, output_code = run_mover(input_code, ["A=B"])

    assert result.returncode == 0
    assert output_code == expected_output


def test_multiple_prefixes() -> None:
    """Test with multiple prefixes"""
    input_code = """
import A.foo # some comment

import C.baz
import abc.de.baz
import abe.de.baz
import ghi

# no changes
import aghi
import a.ghi
import a.ghi.foo

"""
    expected_output = """
import B.foo # some comment

import D.baz
import foo.bar.de.baz
import foe.baz
import foo.ghi

# no changes
import aghi
import a.ghi
import a.ghi.foo

"""

    result, output_code = run_mover(
        input_code, ["A=B", "C=D", "abc=foo.bar", "abe.de=foe", "ghi=foo.ghi"]
    )

    assert result.returncode == 0
    assert output_code == expected_output


def test_invalid_prefix_format() -> None:
    """Test invalid prefix format raises error"""
    result, _ = run_mover("import A.foo", ["AB"])

    assert result.returncode != 0
    assert "Invalid prefix format" in result.stderr


def test_no_transformation_needed() -> None:
    """Test that code remains the same if no matching prefixes"""
    input_code = "import X.y.z"
    expected_output = "import X.y.z"

    result, output_code = run_mover(input_code, ["A=B"])

    assert result.returncode == 0
    assert output_code == expected_output
