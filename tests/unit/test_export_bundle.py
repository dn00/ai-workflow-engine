"""Tests for export_bundle CLI script."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.bundle.models import BundleError, ReplayBundle
from app.core.enums import ActorType, EventType, RunMode, RunStatus
from app.core.models import Event, Run, VersionInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(run_id: str = "run-1") -> Run:
    return Run(
        run_id=run_id,
        workflow_type="access_request",
        status=RunStatus.COMPLETED,
        mode=RunMode.LIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _make_event(run_id: str, seq: int) -> Event:
    return Event(
        event_id=f"evt-{seq}",
        run_id=run_id,
        seq=seq,
        event_type=EventType.PROPOSAL_GENERATED,
        actor_type=ActorType.SYSTEM,
        payload={"key": "value"},
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        version_info=VersionInfo(schema_version="1.0", created_by="test"),
    )


def _make_bundle(run_id: str = "run-1") -> ReplayBundle:
    return ReplayBundle(
        bundle_version="1.0",
        exported_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        run=_make_run(run_id),
        events=[_make_event(run_id, 1)],
        receipt=None,
        projection=None,
    )


# ---------------------------------------------------------------------------
# Export writes JSON file
# ---------------------------------------------------------------------------

def test_export_writes_json_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    bundle = _make_bundle("test-run")

    with patch("scripts.export_bundle.assemble_bundle", return_value=bundle), \
         patch("scripts.export_bundle.get_engine"), \
         patch("scripts.export_bundle.get_session_factory"), \
         patch("scripts.export_bundle.enable_sqlite_fk_pragma"), \
         patch("scripts.export_bundle.SQLiteRunRepository"), \
         patch("scripts.export_bundle.SQLiteEventRepository"), \
         patch("scripts.export_bundle.SQLiteReceiptRepository"):
        from scripts.export_bundle import export_bundle
        path = export_bundle("test-run")

    assert Path(path).exists()
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Export contains bundle fields
# ---------------------------------------------------------------------------

def test_export_contains_bundle_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    bundle = _make_bundle("test-run")

    with patch("scripts.export_bundle.assemble_bundle", return_value=bundle), \
         patch("scripts.export_bundle.get_engine"), \
         patch("scripts.export_bundle.get_session_factory"), \
         patch("scripts.export_bundle.enable_sqlite_fk_pragma"), \
         patch("scripts.export_bundle.SQLiteRunRepository"), \
         patch("scripts.export_bundle.SQLiteEventRepository"), \
         patch("scripts.export_bundle.SQLiteReceiptRepository"):
        from scripts.export_bundle import export_bundle
        path = export_bundle("test-run")

    with open(path) as f:
        data = json.load(f)

    expected_keys = {"bundle_version", "exported_at", "run", "events", "receipt", "projection"}
    assert expected_keys.issubset(data.keys())


# ---------------------------------------------------------------------------
# DB_URL override
# ---------------------------------------------------------------------------

def test_export_custom_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    bundle = _make_bundle("test-run")
    custom_url = "sqlite:///custom/path.db"

    mock_engine = MagicMock()
    with patch("scripts.export_bundle.assemble_bundle", return_value=bundle), \
         patch("scripts.export_bundle.get_engine", return_value=mock_engine) as mock_get_engine, \
         patch("scripts.export_bundle.get_session_factory"), \
         patch("scripts.export_bundle.enable_sqlite_fk_pragma"), \
         patch("scripts.export_bundle.SQLiteRunRepository"), \
         patch("scripts.export_bundle.SQLiteEventRepository"), \
         patch("scripts.export_bundle.SQLiteReceiptRepository"):
        from scripts.export_bundle import export_bundle
        export_bundle("test-run", db_url=custom_url)

    mock_get_engine.assert_called_once_with(custom_url)


# ---------------------------------------------------------------------------
# bundles/ dir doesn't exist
# ---------------------------------------------------------------------------

def test_export_creates_bundles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    bundle = _make_bundle("test-run")

    assert not (tmp_path / "bundles").exists()

    with patch("scripts.export_bundle.assemble_bundle", return_value=bundle), \
         patch("scripts.export_bundle.get_engine"), \
         patch("scripts.export_bundle.get_session_factory"), \
         patch("scripts.export_bundle.enable_sqlite_fk_pragma"), \
         patch("scripts.export_bundle.SQLiteRunRepository"), \
         patch("scripts.export_bundle.SQLiteEventRepository"), \
         patch("scripts.export_bundle.SQLiteReceiptRepository"):
        from scripts.export_bundle import export_bundle
        export_bundle("test-run")

    assert (tmp_path / "bundles").exists()


# ---------------------------------------------------------------------------
# Unknown run_id
# ---------------------------------------------------------------------------

def test_export_unknown_run_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)

    with patch("scripts.export_bundle.get_engine"), \
         patch("scripts.export_bundle.get_session_factory"), \
         patch("scripts.export_bundle.enable_sqlite_fk_pragma"), \
         patch("scripts.export_bundle.SQLiteRunRepository"), \
         patch("scripts.export_bundle.SQLiteEventRepository"), \
         patch("scripts.export_bundle.SQLiteReceiptRepository"), \
         patch("scripts.export_bundle.assemble_bundle", side_effect=BundleError("Run not found: nonexistent")):
        from scripts.export_bundle import export_bundle
        with pytest.raises(BundleError, match="Run not found"):
            export_bundle("nonexistent")


# ---------------------------------------------------------------------------
# No RUN_ID argument
# ---------------------------------------------------------------------------

def test_export_no_args_usage():
    result = subprocess.run(
        [sys.executable, "-m", "scripts.export_bundle"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Usage:" in result.stderr
