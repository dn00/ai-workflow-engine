"""Abstract effect adapter and precondition guard (INV-4.2).

Provides the base interface for side-effect execution and the guard function
that enforces preconditions before any effect can run.
"""

from abc import ABC, abstractmethod

from app.core.enums import RunMode, RunStatus


class EffectPreconditionError(Exception):
    """Raised when effect preconditions (INV-4.2) are not met."""


class AbstractEffectAdapter(ABC):
    """Abstract base class for effect adapters.

    Subclasses must implement execute() to perform the actual side effect.
    """

    @abstractmethod
    def execute(self, run_id: str, idempotency_key: str) -> dict:
        """Execute the effect and return a receipt dict."""
        ...


def check_effect_preconditions(
    status: RunStatus,
    mode: RunMode,
    idempotency_key: str | None,
) -> None:
    """Enforce INV-4.2 preconditions 1, 3, 4.

    Precondition 2 (effect.requested emitted) is a caller-contract obligation.

    Raises:
        EffectPreconditionError: If any condition is unmet.
    """
    if status != RunStatus.APPROVED:
        raise EffectPreconditionError(
            f"Run status must be approved, got {status.value}"
        )
    if mode != RunMode.LIVE:
        raise EffectPreconditionError(
            f"Run mode must be live, got {mode.value}"
        )
    if idempotency_key is None:
        raise EffectPreconditionError(
            "Idempotency key is required for effect execution"
        )
