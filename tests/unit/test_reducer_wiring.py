"""Tests for reducer-projection wiring."""

import json

import pytest
from pydantic import ValidationError

from app.core.enums import RunStatus


class TestRunProjectionImportableFromCore:
    def test_run_projection_importable_from_core(self) -> None:
        from app.core import RunProjection

        proj = RunProjection(run_id="run-1")
        assert proj.run_id == "run-1"
        assert proj.status == RunStatus.RECEIVED


class TestReduceEventsImportableFromCore:
    def test_reduce_events_importable_from_core(self) -> None:
        from app.core import reduce_events

        assert callable(reduce_events)


class TestReducerErrorImportableFromCore:
    def test_reducer_error_importable_from_core(self) -> None:
        from app.core import ReducerError

        assert issubclass(ReducerError, Exception)


class TestProjectionRoundTrip:
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


class TestProjectionDictJsonSerializable:
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


class TestInvalidStatusRaisesValidationError:
    def test_invalid_status_raises_validation_error(self) -> None:
        from app.core import RunProjection

        with pytest.raises(ValidationError):
            RunProjection(run_id="run-1", status="not_a_valid_status")  # type: ignore[arg-type]
