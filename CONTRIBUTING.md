# Contribution Guide

We appreciate your interest in contributing! Here’s how you can get involved.

## 🐞 Reporting Issues

### Security Vulnerabilities

If you discover a security issue, please report it promptly via the GitHub ["Report a Vulnerability"][new-security] tab.
For more details on our security policies, see [SECURITY.md](SECURITY.md).

### Bugs

Found a bug?
Before opening a new issue, please check the [existing issues][issues] to see if it’s already been reported.
If it’s a new bug, you can [create an issue here][new-issue].

### Feature Requests

Got an idea for a new feature? We’d love to hear it!
Please [submit a feature request][new-issue] and provide as much detail as possible.

## 🛠️ Contributing Code

If you’d like to contribute code, follow these steps:

1. **Open an Issue:** Start by [opening an issue][new-issue] to discuss your proposal or bug fix.
2. **Fork the Repository:** Create a fork and work on your changes in a new branch.
3. **Submit a Pull Request:** Once your changes are ready, submit a Pull Request (PR) for review.

## 💻 Development Setup

To set up your development environment, ensure you have the following tools installed:

- Python 3.10 or later
- Make
- Python Setuptools (may be inside virtualenv)

Then, install the module for edit with the required dependencies:

```bash
pip install -e .[dev,genproto,gendoc]
```

On Windows, you will have to add another dependency:

```bash
pip install -e .[dev,genproto,windows,gendoc]
```

## 🧪 Testing

### Writing Tests

All new code must include unit tests to ensure coverage and stability.

### Running Tests

Run the tests locally with:

```bash
tox
```

## 🔍 Code Quality

### Linting

Ensure your code meets project standards by running the linter:

```bash
pre-commit run --all && tox
```

## 📋 Makefile Commands

To see a list of available `make` commands, run:

```bash
make help
```


[issues]: https://github.com/nebius/pysdk/issues
[new-issue]: https://github.com/nebius/pysdk/issues/new/choose
[new-security]: https://github.com/nebius/pysdk/security/advisories/new
