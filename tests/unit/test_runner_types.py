"""Tests for runner types."""

import pytest

from app.core.runners import AbstractRunner, RunResult, RunnerError


# ---------------------------------------------------------------------------
# AbstractRunner defines 3 abstract methods
# ---------------------------------------------------------------------------


def test_abstract_runner_defines_three_abstract_methods():
    abstracts = getattr(AbstractRunner, "__abstractmethods__", set())
    assert "start_run" in abstracts
    assert "submit_review" in abstracts
    assert "replay_run" in abstracts
    assert len(abstracts) == 3


# ---------------------------------------------------------------------------
# RunResult model fields
# ---------------------------------------------------------------------------


def test_run_result_fields():
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
# RunnerError is importable
# ---------------------------------------------------------------------------


def test_runner_error_importable():
    with pytest.raises(Exception, match="test message"):
        raise RunnerError("test message")


# ---------------------------------------------------------------------------
# RunResult with None review_task
# ---------------------------------------------------------------------------


def test_run_result_default_review_task():
    from app.core.models import Run
    from app.core.projections.models import RunProjection

    run = Run(run_id="r1")
    proj = RunProjection(run_id="r1")

    result = RunResult(run=run, projection=proj)
    assert result.review_task is None


# ---------------------------------------------------------------------------
# AbstractRunner direct instantiation
# ---------------------------------------------------------------------------


def test_abstract_runner_cannot_instantiate():
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        AbstractRunner()
