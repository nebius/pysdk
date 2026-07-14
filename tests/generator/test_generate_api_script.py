"""Recovery and comparison tests for the staged API updater."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scripts import generate_api


def _configure_paths(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(generate_api, "TARGET_API", root / "live")
    monkeypatch.setattr(generate_api, "BACKUP_API", root / "backup")
    monkeypatch.setattr(generate_api, "RETIRED_API", root / "retired")
    monkeypatch.setattr(generate_api, "PROMOTION_MARKER", root / "marker")


def _tree(path: Path, content: str) -> None:
    path.mkdir(parents=True)
    (path / "value.py").write_text(content)


def test_same_tree_detects_content_additions_and_deletions(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    _tree(left, "same\n")
    _tree(right, "same\n")
    assert generate_api.same_tree(left, right)
    (right / "extra.py").write_text("extra\n")
    assert not generate_api.same_tree(left, right)


def test_recover_restores_backup_after_interrupted_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    _tree(generate_api.TARGET_API, "new\n")
    _tree(generate_api.BACKUP_API, "old\n")
    generate_api.PROMOTION_MARKER.write_text("promotion in progress\n")

    generate_api.recover()

    assert (generate_api.TARGET_API / "value.py").read_text() == "old\n"
    assert not generate_api.BACKUP_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()


def test_promote_restores_live_tree_when_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    staged = tmp_path / "staged"
    _tree(generate_api.TARGET_API, "old\n")
    _tree(staged, "new\n")

    def fail(_: Path) -> None:
        raise RuntimeError("invalid staged tree")

    monkeypatch.setattr(generate_api, "validate", fail)
    with pytest.raises(RuntimeError, match="invalid staged tree"):
        generate_api.promote(staged)

    assert (generate_api.TARGET_API / "value.py").read_text() == "old\n"
    assert not generate_api.BACKUP_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()


def test_promote_replaces_complete_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    staged = tmp_path / "staged"
    _tree(generate_api.TARGET_API, "old\n")
    _tree(staged, "new\n")
    monkeypatch.setattr(generate_api, "validate", lambda _: None)

    generate_api.promote(staged)

    assert (generate_api.TARGET_API / "value.py").read_text() == "new\n"
    assert not generate_api.BACKUP_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()


def test_failed_rollback_keeps_recovery_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    staged = tmp_path / "staged"
    _tree(generate_api.TARGET_API, "old\n")
    _tree(staged, "new\n")
    monkeypatch.setattr(
        generate_api,
        "validate",
        lambda _: (_ for _ in ()).throw(RuntimeError("invalid")),
    )
    original_rename = Path.rename
    failed = False

    def fail_once(path: Path, target: Path) -> Path:
        nonlocal failed
        if (
            path == generate_api.BACKUP_API
            and target == generate_api.TARGET_API
            and not failed
        ):
            failed = True
            raise OSError("rollback interrupted")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_once)
    with pytest.raises(OSError, match="rollback interrupted"):
        generate_api.promote(staged)
    assert generate_api.PROMOTION_MARKER.exists()
    assert generate_api.BACKUP_API.exists()

    generate_api.recover()
    assert (generate_api.TARGET_API / "value.py").read_text() == "old\n"
    assert not generate_api.PROMOTION_MARKER.exists()


def test_failed_backup_retirement_rolls_back_immediately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    staged = tmp_path / "staged"
    _tree(generate_api.TARGET_API, "old\n")
    _tree(staged, "new\n")
    monkeypatch.setattr(generate_api, "validate", lambda _: None)
    original_rename = Path.rename
    failed = False

    def fail_once(path: Path, target: Path) -> Path:
        nonlocal failed
        if (
            path == generate_api.BACKUP_API
            and target == generate_api.RETIRED_API
            and not failed
        ):
            failed = True
            raise OSError("retirement interrupted")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_once)
    with pytest.raises(OSError, match="retirement interrupted"):
        generate_api.promote(staged)
    assert (generate_api.TARGET_API / "value.py").read_text() == "old\n"
    assert not generate_api.PROMOTION_MARKER.exists()


def test_recover_restores_retired_backup_before_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    _tree(generate_api.TARGET_API, "new\n")
    _tree(generate_api.RETIRED_API, "old\n")
    generate_api.PROMOTION_MARKER.write_text("promotion in progress\n")

    generate_api.recover()

    assert (generate_api.TARGET_API / "value.py").read_text() == "old\n"
    assert not generate_api.RETIRED_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()


def test_failed_first_rename_preserves_live_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    staged = tmp_path / "staged"
    _tree(generate_api.TARGET_API, "old\n")
    _tree(staged, "new\n")
    original_rename = Path.rename

    def fail_live_rename(path: Path, target: Path) -> Path:
        if path == generate_api.TARGET_API and target == generate_api.BACKUP_API:
            raise OSError("live rename failed")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_live_rename)
    with pytest.raises(OSError, match="live rename failed"):
        generate_api.promote(staged)

    assert (generate_api.TARGET_API / "value.py").read_text() == "old\n"
    assert not generate_api.BACKUP_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()


def test_check_mode_refuses_recovery_without_mutating_live_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(generate_api, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(generate_api, "STAGING_PARENT", tmp_path / "runs")
    _tree(generate_api.TARGET_API, "new\n")
    _tree(generate_api.BACKUP_API, "old\n")
    generate_api.PROMOTION_MARKER.write_text("promotion in progress\n")
    monkeypatch.setattr(sys, "argv", ["generate_api.py", "--check"])

    with pytest.raises(RuntimeError, match="recovery is required"):
        generate_api.main()

    assert (generate_api.TARGET_API / "value.py").read_text() == "new\n"
    assert (generate_api.BACKUP_API / "value.py").read_text() == "old\n"
    assert generate_api.PROMOTION_MARKER.exists()


def test_check_mode_rejects_cache_overlapping_live_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(generate_api, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(generate_api, "STAGING_PARENT", tmp_path / "runs")
    _tree(generate_api.TARGET_API, "live\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_api.py",
            "--check",
            "--cache-dir",
            str(generate_api.TARGET_API),
        ],
    )

    with pytest.raises(ValueError, match="overlaps"):
        generate_api.main()

    assert list(generate_api.TARGET_API.iterdir()) == [
        generate_api.TARGET_API / "value.py"
    ]


def test_validate_only_generates_without_comparing_or_promoting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(generate_api, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(generate_api, "STAGING_PARENT", tmp_path / "runs")
    _tree(generate_api.TARGET_API, "live\n")
    generated = tmp_path / "generated"
    _tree(generated, "candidate\n")
    monkeypatch.setattr(generate_api, "generate", lambda *args: generated)
    monkeypatch.setattr(
        generate_api,
        "same_tree",
        lambda *args: (_ for _ in ()).throw(AssertionError("comparison ran")),
    )
    monkeypatch.setattr(
        generate_api,
        "promote",
        lambda *args: (_ for _ in ()).throw(AssertionError("promotion ran")),
    )
    monkeypatch.setattr(sys, "argv", ["generate_api.py", "--validate-only"])

    assert generate_api.main() == 0
    assert (generate_api.TARGET_API / "value.py").read_text() == "live\n"


def test_update_regenerates_with_promoted_api_before_retiring_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(generate_api, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(generate_api, "STAGING_PARENT", tmp_path / "runs")
    _tree(generate_api.TARGET_API, "old\n")
    calls = 0

    def generate(
        _partition: str,
        _jobs: int,
        run_root: Path,
        _cache_dir: Path | None,
    ) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            assert (generate_api.TARGET_API / "value.py").read_text() == "new\n"
            assert (generate_api.BACKUP_API / "value.py").read_text() == "old\n"
        output = run_root / "src" / "nebius" / "api"
        _tree(output, "new\n")
        return output

    monkeypatch.setattr(generate_api, "generate", generate)
    monkeypatch.setattr(generate_api, "validate", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["generate_api.py"])

    assert generate_api.main() == 0
    assert calls == 2
    assert (generate_api.TARGET_API / "value.py").read_text() == "new\n"
    assert not generate_api.BACKUP_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()


def test_unchanged_update_still_promotes_and_regenerates_under_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(generate_api, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(generate_api, "STAGING_PARENT", tmp_path / "runs")
    _tree(generate_api.TARGET_API, "same\n")
    calls = 0

    def generate(
        _partition: str,
        _jobs: int,
        run_root: Path,
        _cache_dir: Path | None,
    ) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            assert (generate_api.TARGET_API / "value.py").read_text() == "same\n"
            assert (generate_api.BACKUP_API / "value.py").read_text() == "same\n"
        output = run_root / "src" / "nebius" / "api"
        _tree(output, "same\n")
        return output

    monkeypatch.setattr(generate_api, "generate", generate)
    monkeypatch.setattr(generate_api, "validate", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["generate_api.py"])

    assert generate_api.main() == 0
    assert calls == 2
    assert (generate_api.TARGET_API / "value.py").read_text() == "same\n"
    assert not generate_api.BACKUP_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()


def test_update_restores_committed_api_when_promoted_generator_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(generate_api, "LOCK", tmp_path / "lock")
    monkeypatch.setattr(generate_api, "STAGING_PARENT", tmp_path / "runs")
    _tree(generate_api.TARGET_API, "old\n")
    calls = 0

    def generate(
        _partition: str,
        _jobs: int,
        run_root: Path,
        _cache_dir: Path | None,
    ) -> Path:
        nonlocal calls
        calls += 1
        if calls == 2:
            assert (generate_api.TARGET_API / "value.py").read_text() == "new\n"
            assert (generate_api.BACKUP_API / "value.py").read_text() == "old\n"
            raise RuntimeError("promoted generator failed")
        output = run_root / "src" / "nebius" / "api"
        _tree(output, "new\n")
        return output

    monkeypatch.setattr(generate_api, "generate", generate)
    monkeypatch.setattr(generate_api, "validate", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["generate_api.py"])

    with pytest.raises(RuntimeError, match="promoted generator failed"):
        generate_api.main()

    assert calls == 2
    assert (generate_api.TARGET_API / "value.py").read_text() == "old\n"
    assert not generate_api.BACKUP_API.exists()
    assert not generate_api.PROMOTION_MARKER.exists()
