"""Tests for runner barrel export wiring."""


def test_runners_package_exports():
    """Verify app.core.runners exports all expected symbols."""
    from app.core.runners import AbstractRunner, LocalRunner, RunResult, RunnerError

    assert AbstractRunner is not None
    assert LocalRunner is not None
    assert RunResult is not None
    assert RunnerError is not None


def test_core_package_exports_runner_types():
    """Verify app.core re-exports runner types."""
    from app.core import AbstractRunner, LocalRunner, RunResult, RunnerError

    assert AbstractRunner is not None
    assert LocalRunner is not None
    assert RunResult is not None
    assert RunnerError is not None
