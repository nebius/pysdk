import sys

import tomlkit


# Function to increment version parts
def increment_version(version: str, part: str) -> str:
    major, minor, patch = map(int, version.split("."))

    if part == "major":
        major += 1
        minor, patch = 0, 0
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "patch":
        patch += 1
    else:
        raise ValueError(
            f"Invalid part: {part}. Expected 'major', 'minor', or 'patch'.",
        )

    return f"{major}.{minor}.{patch}"


# Main script
def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: python version_updater.py <path_to_pyproject.toml>"
            + " <path_to_version.py>"
            + " <major|minor|patch|print>",
        )
        sys.exit(1)

    file_path = sys.argv[1]
    version_file_path = sys.argv[2]
    part = sys.argv[3]

    try:
        # Read pyproject.toml
        with open(file_path, "r") as file:
            data = tomlkit.parse(file.read())

        version = data["project"]["version"]  # type: ignore
        if part == "print":
            print(f"{version}")
            return

        updated_version = increment_version(version, part)  # type: ignore
        data["project"]["version"] = updated_version  # type: ignore

        with open(version_file_path, "w") as version_file:
            version_file.write(f'version = "{updated_version}"' + "\n")

        # Write the updated pyproject.toml back
        with open(file_path, "w") as file:
            tomlkit.dump(data, file)  # type: ignore[unused-ignore]

        print(f"Updated version: {version} -> {updated_version}")
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
    except KeyError:
        print("Error: Could not find 'tool.poetry.version' in the TOML file.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
