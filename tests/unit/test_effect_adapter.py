"""Unit tests for the effect adapter interface and precondition guard."""

from datetime import datetime

import pytest

from app.core.enums import RunMode, RunStatus
from app.effects.base import (
    AbstractEffectAdapter,
    EffectPreconditionError,
    check_effect_preconditions,
)
from app.effects.simulated import SimulatedEffectAdapter


class TestAbstractEffectAdapter:
    """Task001 AC-1 test_abstract_adapter_cannot_be_instantiated"""

    def test_abstract_adapter_cannot_be_instantiated(self):
        """AC-1: AbstractEffectAdapter cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractEffectAdapter()


class TestGuardPassesValidInputs:
    """Task001 AC-2 test_guard_passes_valid_inputs"""

    def test_guard_passes_valid_inputs(self):
        """AC-2: Guard returns None for valid inputs."""
        result = check_effect_preconditions(
            status=RunStatus.APPROVED,
            mode=RunMode.LIVE,
            idempotency_key="key-123",
        )
        assert result is None


class TestGuardRejectsNonApprovedStatuses:
    """Task001 EC-1 test_guard_rejects_non_approved_statuses"""

    @pytest.mark.parametrize(
        "status",
        [RunStatus.RECEIVED, RunStatus.VALIDATED, RunStatus.REJECTED, RunStatus.EFFECT_PENDING],
    )
    def test_guard_rejects_non_approved_statuses(self, status: RunStatus):
        """EC-1: Guard rejects multiple non-APPROVED statuses."""
        with pytest.raises(EffectPreconditionError):
            check_effect_preconditions(
                status=status,
                mode=RunMode.LIVE,
                idempotency_key="key-123",
            )


class TestGuardRejectsNonLiveModes:
    """Task001 EC-2 test_guard_rejects_non_live_modes"""

    @pytest.mark.parametrize("mode", [RunMode.DRY_RUN, RunMode.REPLAY])
    def test_guard_rejects_non_live_modes(self, mode: RunMode):
        """EC-2: Guard rejects both non-LIVE modes."""
        with pytest.raises(EffectPreconditionError):
            check_effect_preconditions(
                status=RunStatus.APPROVED,
                mode=mode,
                idempotency_key="key-123",
            )


class TestGuardWrongStatusErrorMessage:
    """Task001 ERR-1 test_guard_wrong_status_error_message"""

    def test_guard_wrong_status_error_message(self):
        """ERR-1: Error message contains 'approved' and actual status."""
        with pytest.raises(EffectPreconditionError, match="approved") as exc_info:
            check_effect_preconditions(
                status=RunStatus.REJECTED,
                mode=RunMode.LIVE,
                idempotency_key="k",
            )
        assert "rejected" in str(exc_info.value).lower()


class TestGuardWrongModeErrorMessage:
    """Task001 ERR-2 test_guard_wrong_mode_error_message"""

    def test_guard_wrong_mode_error_message(self):
        """ERR-2: Error message contains 'live' and actual mode."""
        with pytest.raises(EffectPreconditionError, match="(?i)live") as exc_info:
            check_effect_preconditions(
                status=RunStatus.APPROVED,
                mode=RunMode.DRY_RUN,
                idempotency_key="k",
            )
        assert "dry_run" in str(exc_info.value).lower()


class TestGuardMissingKeyErrorMessage:
    """Task001 ERR-3 test_guard_missing_key_error_message"""

    def test_guard_missing_key_error_message(self):
        """ERR-3: Error message contains 'idempotency'."""
        with pytest.raises(EffectPreconditionError, match="(?i)idempotency"):
            check_effect_preconditions(
                status=RunStatus.APPROVED,
                mode=RunMode.LIVE,
                idempotency_key=None,
            )


class TestSimulatedReceiptHasRequiredFields:
    """Task002 AC-1 test_simulated_receipt_has_required_fields"""

    def test_simulated_receipt_has_required_fields(self):
        """AC-1: Receipt contains required keys."""
        adapter = SimulatedEffectAdapter()
        receipt = adapter.execute("run-1", "key-1")
        assert "effect" in receipt
        assert "run_id" in receipt
        assert "idempotency_key" in receipt
        assert "timestamp" in receipt
        assert "simulated" in receipt


class TestSimulatedAdapterIsAbstractSubclass:
    """Task002 AC-2 test_simulated_adapter_is_abstract_subclass"""

    def test_simulated_adapter_is_abstract_subclass(self):
        """AC-2: SimulatedEffectAdapter is an AbstractEffectAdapter."""
        adapter = SimulatedEffectAdapter()
        assert isinstance(adapter, AbstractEffectAdapter)


class TestBarrelExportsAllPublicNames:
    """Task002 AC-3 test_barrel_exports_all_public_names"""

    def test_barrel_exports_all_public_names(self):
        """AC-3: All public names importable from app.effects."""
        from app.effects import (  # noqa: F401
            AbstractEffectAdapter,
            EffectPreconditionError,
            SimulatedEffectAdapter,
            check_effect_preconditions,
        )


class TestSimulatedReceiptValuesCorrect:
    """Task002 EC-1 test_simulated_receipt_values_correct"""

    def test_simulated_receipt_values_correct(self):
        """EC-1: Receipt values match inputs and spec."""
        adapter = SimulatedEffectAdapter()
        receipt = adapter.execute("run-abc", "idem-xyz")
        assert receipt["effect"] == "create_simulated_approval_task"
        assert receipt["run_id"] == "run-abc"
        assert receipt["idempotency_key"] == "idem-xyz"
        assert receipt["simulated"] is True
        # Verify timestamp is valid ISO 8601
        datetime.fromisoformat(receipt["timestamp"])


class TestSimulatedExecuteRejectsEmptyRunId:
    """Task002 ERR-1 test_simulated_execute_rejects_empty_run_id"""

    def test_simulated_execute_rejects_empty_run_id(self):
        """ERR-1: Execute raises ValueError on empty run_id."""
        adapter = SimulatedEffectAdapter()
        with pytest.raises(ValueError, match="run_id"):
            adapter.execute("", "key-1")
