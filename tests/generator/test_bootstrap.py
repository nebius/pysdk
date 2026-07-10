from pathlib import Path

import pytest

from scripts.bootstrap_generator import promote_candidate
from scripts.generate_api import recover_interrupted_promotion


def test_failed_bootstrap_validation_keeps_live_file(tmp_path: Path) -> None:
    target = tmp_path / "annotations_pb2.py"
    target.write_bytes(b"known-good")
    candidate = tmp_path / "candidate.py"
    candidate.write_bytes(b"broken")

    def reject(_: Path) -> None:
        raise RuntimeError("injected validation failure")

    with pytest.raises(RuntimeError, match="injected validation failure"):
        promote_candidate(candidate, target, reject)

    assert target.read_bytes() == b"known-good"


def test_unchanged_bootstrap_is_not_replaced(tmp_path: Path) -> None:
    target = tmp_path / "annotations_pb2.py"
    target.write_bytes(b"same")
    candidate = tmp_path / "candidate.py"
    candidate.write_bytes(b"same")

    assert promote_candidate(candidate, target, lambda _: None) is False
    assert target.read_bytes() == b"same"


def test_interrupted_api_promotion_is_recovered(tmp_path: Path) -> None:
    target = tmp_path / "api"
    backup = tmp_path / "api-backup"
    backup.mkdir()
    (backup / "marker").write_text("last-known-good")

    assert recover_interrupted_promotion(target, backup)
    assert (target / "marker").read_text() == "last-known-good"
    assert not backup.exists()


def test_completed_api_promotion_discards_stale_backup(tmp_path: Path) -> None:
    target = tmp_path / "api"
    backup = tmp_path / "api-backup"
    target.mkdir()
    backup.mkdir()

    assert not recover_interrupted_promotion(target, backup)
    assert target.is_dir()
    assert not backup.exists()
