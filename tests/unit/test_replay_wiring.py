"""Tests for replay wiring (Feature 011, Batch 02, Task 002)."""


class TestReplayBarrelExports:
    """Task002 AC-1 test_replay_barrel_exports"""

    def test_replay_barrel_exports(self) -> None:
        from app.core.replay import ReplayResult, replay_run

        assert ReplayResult is not None
        assert replay_run is not None


class TestCoreBarrelReExports:
    """Task002 AC-2 test_core_barrel_re_exports"""

    def test_core_barrel_re_exports(self) -> None:
        from app.core import ReplayResult, replay_run

        assert ReplayResult is not None
        assert replay_run is not None


class TestAllListCompleteness:
    """Task002 EC-1 test_all_list_completeness"""

    def test_all_list_completeness(self) -> None:
        import app.core
        import app.core.replay

        assert "ReplayResult" in app.core.replay.__all__
        assert "replay_run" in app.core.replay.__all__
        assert "ReplayResult" in app.core.__all__
        assert "replay_run" in app.core.__all__


class TestNoCircularImport:
    """Task002 ERR-1 test_no_circular_import"""

    def test_no_circular_import(self) -> None:
        # replay imports from projections; projections must not import replay
        import app.core.replay  # noqa: F401 — just verify no ImportError
