"""Retry transient downloads during CI preparation. Run each check once."""

from __future__ import annotations

import argparse
import contextlib
import os
import re
import signal
import subprocess
import sys
import time

RETRY_DELAYS = (2, 5, 10)
INSTALL_TIMEOUT = 300
NETWORK_ERROR = re.compile(
    r"ReadTimeoutError|ConnectTimeoutError|ConnectionResetError|"
    r"Connection broken|Temporary failure in name resolution|"
    r"Connection (?:reset|aborted)|TLS handshake timeout|"
    r"IncompleteRead|incomplete-download|Network is unreachable|"
    r"(?:408|429|500|502|503|504) Server Error|"
    r"too many (?:408|429|500|502|503|504) error responses|"
    r"ECONNRESET|ETIMEDOUT|EAI_AGAIN|HTTP Error (?:408|429|500|502|503|504)",
    re.IGNORECASE,
)
FINAL_ERROR = re.compile(
    r"CERTIFICATE_VERIFY_FAILED|certificate verify failed|"
    r"401 Client Error|403 Client Error|ResolutionImpossible|"
    r"conflicting dependencies|requires a different Python|"
    r"SIGSEGV|Segmentation fault|code -11|E401|E403|"
    r"ERR_TLS_CERT_ALTNAME_INVALID|UNABLE_TO_VERIFY_LEAF_SIGNATURE",
    re.IGNORECASE,
)


def install(command: list[str]) -> int:
    """Retry installation within one shared time budget."""
    deadline = time.monotonic() + INSTALL_TIMEOUT
    environment = dict(
        os.environ, PIP_RETRIES="0", PIP_RESUME_RETRIES="0", PIP_TIMEOUT="30", PIP_DISABLE_PIP_VERSION_CHECK="1"
    )
    for attempt in range(len(RETRY_DELAYS) + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return 124
        with subprocess.Popen(
            command,  # noqa: S603
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=environment,
            start_new_session=True,
        ) as process:
            try:
                output, _ = process.communicate(timeout=remaining)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                output, _ = process.communicate()
                sys.stdout.write(output)
                sys.stdout.flush()
                return 124
            except BaseException:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        sys.stdout.write(output)
        sys.stdout.flush()
        status = process.returncode
        if status <= 0 or FINAL_ERROR.search(output) or not NETWORK_ERROR.search(output):
            return status
        if attempt == len(RETRY_DELAYS):
            return status
        delay = min(RETRY_DELAYS[attempt], max(0, deadline - time.monotonic()))
        sys.stderr.write(f"Network failure during installation. Retry {attempt + 1}/3 in {delay}s.\n")
        time.sleep(delay)
    message = "Invalid installation attempt limit"
    raise AssertionError(message)


def run_tox(environments: list[str]) -> int:
    """Prepare each environment before executing its commands once."""
    result = 0
    for environment in environments:
        command = [sys.executable, "-m", "tox", "run", "-e", environment]
        status = install([*command, "--notest"])
        if status == 0 and environment == "type_consumer":
            status = install([sys.executable, "-m", "tox", "exec", "-e", environment, "--", "pyright", "--version"])
        if status == 0:
            status = subprocess.call([*command, "--skip-env-install"])  # noqa: S603
        if status and result == 0:
            result = status
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("install", "tox"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.arguments:
        parser.error("Specify packages or tox environments")
    if args.phase == "install":
        return install([sys.executable, "-m", "pip", "install", *args.arguments])
    return run_tox(args.arguments)


if __name__ == "__main__":
    sys.exit(main())
