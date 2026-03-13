"""Tests for runner types (Feature 009, Batch 01, Task 001)."""

import pytest

from app.core.runners import AbstractRunner, RunResult, RunnerError


# ---------------------------------------------------------------------------
# Task001 AC-1: AbstractRunner defines 3 abstract methods
# ---------------------------------------------------------------------------


def test_Task001_AC_1_test_abstract_runner_defines_three_abstract_methods():
    """Task001 AC-1 test_abstract_runner_defines_three_abstract_methods"""
    abstracts = getattr(AbstractRunner, "__abstractmethods__", set())
    assert "start_run" in abstracts
    assert "submit_review" in abstracts
    assert "replay_run" in abstracts
    assert len(abstracts) == 3


# ---------------------------------------------------------------------------
# Task001 AC-2: RunResult model fields
# ---------------------------------------------------------------------------


def test_Task001_AC_2_test_run_result_fields():
    """Task001 AC-2 test_run_result_fields"""
    from app.core.models import Run, ReviewTask
    from app.core.projections.models import RunProjection

    run = Run(run_id="r1")
    proj = RunProjection(run_id="r1")
    review = ReviewTask(review_id="rev1", run_id="r1")

    result = RunResult(run=run, projection=proj, review_task=review)
    assert result.run is run
    assert result.projection is proj
    assert result.review_task is review


# ---------------------------------------------------------------------------
# Task001 AC-3: RunnerError is importable
# ---------------------------------------------------------------------------


def test_Task001_AC_3_test_runner_error_importable():
    """Task001 AC-3 test_runner_error_importable"""
    with pytest.raises(Exception, match="test message"):
        raise RunnerError("test message")


# ---------------------------------------------------------------------------
# Task001 EC-1: RunResult with None review_task
# ---------------------------------------------------------------------------


def test_Task001_EC_1_test_run_result_default_review_task():
    """Task001 EC-1 test_run_result_default_review_task"""
    from app.core.models import Run
    from app.core.projections.models import RunProjection

    run = Run(run_id="r1")
    proj = RunProjection(run_id="r1")

    result = RunResult(run=run, projection=proj)
    assert result.review_task is None


# ---------------------------------------------------------------------------
# Task001 ERR-1: AbstractRunner direct instantiation
# ---------------------------------------------------------------------------


def test_Task001_ERR_1_test_abstract_runner_cannot_instantiate():
    """Task001 ERR-1 test_abstract_runner_cannot_instantiate"""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        AbstractRunner()
