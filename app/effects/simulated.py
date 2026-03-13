"""Simulated effect adapter — the only MVP effect (INV-4.1).

Returns a receipt dict without performing any real side effect.
"""

from datetime import datetime, timezone

from app.effects.base import AbstractEffectAdapter


class SimulatedEffectAdapter(AbstractEffectAdapter):
    """Simulated effect that returns a receipt without real side effects."""

    def execute(self, run_id: str, idempotency_key: str) -> dict:
        """Return a simulated approval-task receipt.

        Raises:
            ValueError: If run_id is empty.
        """
        if not run_id:
            raise ValueError("run_id must not be empty")
        return {
            "effect": "create_simulated_approval_task",
            "run_id": run_id,
            "idempotency_key": idempotency_key,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }
