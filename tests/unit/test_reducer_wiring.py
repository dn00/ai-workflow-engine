"""Tests for reducer-projection wiring (Feature 008, Batch 02, Task 002)."""

import json

import pytest
from pydantic import ValidationError

from app.core.enums import RunStatus


class TestTask002AC1RunProjectionImportableFromCore:
    """Task002 AC-1 test_run_projection_importable_from_core"""

    def test_run_projection_importable_from_core(self) -> None:
        from app.core import RunProjection

        proj = RunProjection(run_id="run-1")
        assert proj.run_id == "run-1"
        assert proj.status == RunStatus.RECEIVED


class TestTask002AC2ReduceEventsImportableFromCore:
    """Task002 AC-2 test_reduce_events_importable_from_core"""

    def test_reduce_events_importable_from_core(self) -> None:
        from app.core import reduce_events

        assert callable(reduce_events)


class TestTask002AC3ReducerErrorImportableFromCore:
    """Task002 AC-3 test_reducer_error_importable_from_core"""

    def test_reducer_error_importable_from_core(self) -> None:
        from app.core import ReducerError

        assert issubclass(ReducerError, Exception)


class TestTask002AC4ProjectionRoundTrip:
    """Task002 AC-4 test_projection_round_trip"""

    def test_projection_round_trip(self) -> None:
        from app.core import RunProjection

        original = RunProjection(
            run_id="run-1",
            status=RunStatus.COMPLETED,
            proposal={"raw": "text"},
            validation_result={"valid": True},
            policy_decision={"status": "approved", "reason_codes": []},
            review_decision="approve",
            effect_result={"changes": []},
            error=None,
            last_event_seq=7,
            event_count=7,
            version_info={
                "proposal_schema_version": "1.0",
                "prompt_version": "1.0",
                "policy_version": "1.0",
            },
        )
        roundtripped = RunProjection.model_validate(original.model_dump())
        assert roundtripped == original


class TestTask002EC1ProjectionDictJsonSerializable:
    """Task002 EC-1 test_projection_dict_json_serializable"""

    def test_projection_dict_json_serializable(self) -> None:
        from app.core import RunProjection

        proj = RunProjection(
            run_id="run-1",
            status=RunStatus.COMPLETED,
            proposal={"raw": "text"},
            validation_result={"valid": True},
            policy_decision={"status": "approved"},
            review_decision="approve",
            effect_result={"changes": [1, 2]},
            last_event_seq=7,
            event_count=7,
            version_info={"proposal_schema_version": "1.0"},
        )
        dumped = proj.model_dump()
        # Must not raise — all values are JSON-serializable primitives
        serialized = json.dumps(dumped)
        assert isinstance(serialized, str)


class TestTask002ERR1InvalidStatusRaisesValidationError:
    """Task002 ERR-1 test_invalid_status_raises_validation_error"""

    def test_invalid_status_raises_validation_error(self) -> None:
        from app.core import RunProjection

        with pytest.raises(ValidationError):
            RunProjection(run_id="run-1", status="not_a_valid_status")  # type: ignore[arg-type]
