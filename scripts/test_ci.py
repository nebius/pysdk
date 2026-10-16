"""Check the retry boundary between dependency installation and test commands."""

# ruff: noqa: PT009

import sys
import unittest
from unittest import mock

from scripts import ci


class CiTest(unittest.TestCase):
    def test_only_transient_downloads_are_retried(self) -> None:
        for output, attempts in [
            ("ReadTimeoutError while downloading ruff", 4),
            ("CERTIFICATE_VERIFY_FAILED ReadTimeoutError", 1),
            ("ResolutionImpossible", 1),
            ("package does not exist", 1),
            ("ReadTimeoutError then Segmentation fault", 1),
            ("ECONNRESET followed by E401", 1),
        ]:
            with self.subTest(output=output), mock.patch.object(ci.subprocess, "Popen") as popen:
                process = popen.return_value.__enter__.return_value
                process.communicate.return_value = (output, None)
                process.returncode = 1
                with mock.patch.object(ci.time, "sleep"):
                    self.assertEqual(ci.install(["installer"]), 1)
                self.assertEqual(popen.call_count, attempts)

    def test_retries_share_one_installation_deadline(self) -> None:
        with mock.patch.object(ci.subprocess, "Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.communicate.return_value = ("ReadTimeoutError", None)
            process.returncode = 1
            with (
                mock.patch.object(ci.time, "monotonic", side_effect=[0, 1, 2, 301]),
                mock.patch.object(ci.time, "sleep"),
            ):
                self.assertEqual(ci.install(["installer"]), 124)
        self.assertEqual(popen.call_count, 1)

    def test_timeout_remains_124_when_process_exits_before_kill(self) -> None:
        with mock.patch.object(ci.subprocess, "Popen") as popen:
            process = popen.return_value.__enter__.return_value
            process.communicate.side_effect = [ci.subprocess.TimeoutExpired("installer", 300), ("", None)]
            with mock.patch.object(ci.os, "killpg", side_effect=ProcessLookupError):
                self.assertEqual(ci.install(["installer"]), 124)

    def test_check_failure_does_not_repeat_the_check_or_skip_other_environments(self) -> None:
        with (
            mock.patch.object(ci, "install", return_value=0) as install,
            mock.patch.object(
                ci.subprocess,
                "call",
                return_value=1,
            ) as run,
        ):
            self.assertEqual(ci.run_tox(["lint", "type"]), 1)
        install.assert_has_calls(
            [
                mock.call([sys.executable, "-m", "tox", "run", "-e", environment, "--notest"])
                for environment in ["lint", "type"]
            ]
        )
        self.assertEqual(install.call_count, 2)
        run.assert_has_calls(
            [
                mock.call([sys.executable, "-m", "tox", "run", "-e", environment, "--skip-env-install"])
                for environment in ["lint", "type"]
            ]
        )
        self.assertEqual(run.call_count, 2)

    def test_preparation_failure_does_not_execute_the_check(self) -> None:
        with mock.patch.object(ci, "install", return_value=1), mock.patch.object(ci.subprocess, "call") as run:
            self.assertEqual(ci.run_tox(["lint"]), 1)
        run.assert_not_called()

    def test_pyright_download_is_prepared_before_consumer_checks(self) -> None:
        with (
            mock.patch.object(ci, "install", return_value=0) as install,
            mock.patch.object(
                ci.subprocess,
                "call",
                return_value=0,
            ) as run,
        ):
            self.assertEqual(ci.run_tox(["type_consumer"]), 0)
        install.assert_has_calls(
            [
                mock.call([sys.executable, "-m", "tox", "run", "-e", "type_consumer", "--notest"]),
                mock.call([sys.executable, "-m", "tox", "exec", "-e", "type_consumer", "--", "pyright", "--version"]),
            ]
        )
        self.assertEqual(install.call_count, 2)
        run.assert_called_once_with([sys.executable, "-m", "tox", "run", "-e", "type_consumer", "--skip-env-install"])

    def test_failed_pyright_preparation_skips_only_consumer_checks(self) -> None:
        with (
            mock.patch.object(ci, "install", side_effect=[0, 1, 0]),
            mock.patch.object(
                ci.subprocess,
                "call",
                return_value=0,
            ) as run,
        ):
            self.assertEqual(ci.run_tox(["type_consumer", "lint"]), 1)
        run.assert_called_once_with([sys.executable, "-m", "tox", "run", "-e", "lint", "--skip-env-install"])


if __name__ == "__main__":
    unittest.main()
