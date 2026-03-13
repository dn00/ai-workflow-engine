"""Effect adapter module — side-effect boundary (spec §22)."""

from app.effects.base import (
    AbstractEffectAdapter,
    EffectPreconditionError,
    check_effect_preconditions,
)
from app.effects.simulated import SimulatedEffectAdapter

__all__ = [
    "AbstractEffectAdapter",
    "EffectPreconditionError",
    "SimulatedEffectAdapter",
    "check_effect_preconditions",
]
