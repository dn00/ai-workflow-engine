"""Abstract runner interface and error type for the runner layer."""

from abc import ABC, abstractmethod

from app.core.enums import ReviewDecision, RunMode
from app.core.replay.models import ReplayResult


class RunnerError(Exception):
    """Raised when the runner encounters an invalid state or input."""


class AbstractRunner(ABC):
    """Base class for all runner implementations."""

    @abstractmethod
    def start_run(self, input_text: str, mode: RunMode) -> "RunResult":  # noqa: F821
        ...

    @abstractmethod
    def submit_review(self, run_id: str, decision: ReviewDecision) -> "RunResult":  # noqa: F821
        ...

    @abstractmethod
    def replay_run(self, run_id: str) -> ReplayResult:
        ...


# Deferred import to avoid circular dependency — RunResult references models
# that import from this module's siblings.
from app.core.runners.models import RunResult  # noqa: E402, F401

# Update forward refs so the string annotations resolve
AbstractRunner.start_run.__annotations__["return"] = RunResult
AbstractRunner.submit_review.__annotations__["return"] = RunResult
