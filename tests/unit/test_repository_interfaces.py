"""Unit tests for abstract repository interfaces (Feature 005, Batch 01)."""

import inspect
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.enums import ReviewDecision, RunStatus
from app.core.models import Event, ReviewTask, Run
from app.db.repositories.base import (
    AbstractEventRepository,
    AbstractReviewRepository,
    AbstractRunRepository,
    enable_sqlite_fk_pragma,
)

# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestTask001AC1RunRepoAbcNotInstantiable:
    """Task001 AC-1 test_run_repo_abc_not_instantiable"""

    def test_cannot_instantiate_abstract_run_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractRunRepository()  # type: ignore[abstract]


class TestTask001AC2EventRepoAbcNotInstantiable:
    """Task001 AC-2 test_event_repo_abc_not_instantiable"""

    def test_cannot_instantiate_abstract_event_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractEventRepository()  # type: ignore[abstract]


class TestTask001AC3ReviewRepoAbcNotInstantiable:
    """Task001 AC-3 test_review_repo_abc_not_instantiable"""

    def test_cannot_instantiate_abstract_review_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractReviewRepository()  # type: ignore[abstract]


class TestTask001AC4MethodSignaturesUseDomainModels:
    """Task001 AC-4 test_method_signatures_use_domain_models"""

    def test_run_repo_signatures_use_pydantic_models(self) -> None:
        hints = {
            "create": {"run": Run, "return": Run},
            "get": {"run_id": str, "return": Run | None},
            "update_status": {
                "run_id": str,
                "status": RunStatus,
                "updated_at": datetime,
                "return": Run,
            },
            "update_projection": {
                "run_id": str,
                "projection": dict,
                "updated_at": datetime,
                "return": Run,
            },
        }
        for method_name, expected in hints.items():
            method = getattr(AbstractRunRepository, method_name)
            annotations = inspect.get_annotations(method)
            for param, expected_type in expected.items():
                assert param in annotations, (
                    f"{method_name} missing annotation for '{param}'"
                )
                assert annotations[param] == expected_type, (
                    f"{method_name}.{param}: expected {expected_type}, got {annotations[param]}"
                )

    def test_event_repo_signatures_use_pydantic_models(self) -> None:
        hints = {
            "append": {"event": Event, "return": Event},
            "list_by_run": {"run_id": str, "return": list[Event]},
        }
        for method_name, expected in hints.items():
            method = getattr(AbstractEventRepository, method_name)
            annotations = inspect.get_annotations(method)
            for param, expected_type in expected.items():
                assert param in annotations, (
                    f"{method_name} missing annotation for '{param}'"
                )
                assert annotations[param] == expected_type, (
                    f"{method_name}.{param}: expected {expected_type}, got {annotations[param]}"
                )

    def test_review_repo_signatures_use_pydantic_models(self) -> None:
        hints = {
            "create": {"review": ReviewTask, "return": ReviewTask},
            "update_decision": {
                "review_id": str,
                "decision": ReviewDecision,
                "reviewed_at": datetime,
                "return": ReviewTask,
            },
            "get_by_run": {"run_id": str, "return": ReviewTask | None},
        }
        for method_name, expected in hints.items():
            method = getattr(AbstractReviewRepository, method_name)
            annotations = inspect.get_annotations(method)
            for param, expected_type in expected.items():
                assert param in annotations, (
                    f"{method_name} missing annotation for '{param}'"
                )
                assert annotations[param] == expected_type, (
                    f"{method_name}.{param}: expected {expected_type}, got {annotations[param]}"
                )


class TestTask001AC5FkPragmaEnablesForeignKeys:
    """Task001 AC-5 test_fk_pragma_enables_foreign_keys"""

    def test_fk_pragma_returns_1_after_enable(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        enable_sqlite_fk_pragma(engine)
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
            assert result == 1


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestTask001EC1IncompleteSubclassRaisesTypeerror:
    """Task001 EC-1 test_incomplete_subclass_raises_typeerror"""

    def test_subclass_missing_methods_raises_typeerror(self) -> None:
        class PartialRunRepo(AbstractRunRepository):
            def create(self, run: Run) -> Run:
                return run

            def get(self, run_id: str) -> Run | None:
                return None

        with pytest.raises(TypeError) as exc_info:
            PartialRunRepo()  # type: ignore[abstract]

        error_msg = str(exc_info.value)
        assert "update_status" in error_msg or "update_projection" in error_msg


# ---------------------------------------------------------------------------
# ERR Tests
# ---------------------------------------------------------------------------


class TestTask001ERR1DirectInstantiationRaisesTypeerror:
    """Task001 ERR-1 test_direct_instantiation_raises_typeerror"""

    def test_direct_instantiation_error_mentions_abstract_methods(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            AbstractRunRepository()  # type: ignore[abstract]

        error_msg = str(exc_info.value)
        # Python's TypeError for ABCs mentions "abstract" and the method names
        assert "abstract" in error_msg.lower()
        for method in ("create", "get", "update_status", "update_projection"):
            assert method in error_msg, f"Expected '{method}' in error: {error_msg}"
