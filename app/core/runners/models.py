"""Runner result models."""

from pydantic import BaseModel

from app.core.models import ReviewTask, Run
from app.core.projections.models import RunProjection


class RunResult(BaseModel):
    """Result of a runner command (start_run or submit_review)."""

    run: Run
    projection: RunProjection
    review_task: ReviewTask | None = None
