"""Base test fixtures for ai-workflow-engine."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Provide a temporary SQLite database path for tests."""
    return tmp_path / "test.db"
