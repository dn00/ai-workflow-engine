"""Unit tests for abstract repository interfaces."""

import inspect
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text

from app.core.artifacts.models import Artifact
from app.core.enums import ReviewDecision, RunStatus
from app.core.models import Event, ReviewTask, Run
from app.db.repositories.base import (
    AbstractArtifactRepository,
    AbstractEventRepository,
    AbstractLLMTraceRepository,
    AbstractReviewRepository,
    AbstractRunRepository,
    enable_sqlite_fk_pragma,
)
from app.observability.llm_traces import LLMTrace

# ---------------------------------------------------------------------------
# AC Tests
# ---------------------------------------------------------------------------


class TestRunRepoAbcNotInstantiable:
    def test_cannot_instantiate_abstract_run_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractRunRepository()  # type: ignore[abstract]


class TestEventRepoAbcNotInstantiable:
    def test_cannot_instantiate_abstract_event_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractEventRepository()  # type: ignore[abstract]


class TestReviewRepoAbcNotInstantiable:
    def test_cannot_instantiate_abstract_review_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractReviewRepository()  # type: ignore[abstract]


class TestArtifactRepoAbcNotInstantiable:
    def test_cannot_instantiate_abstract_artifact_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractArtifactRepository()  # type: ignore[abstract]


class TestLLMTraceRepoAbcNotInstantiable:
    def test_cannot_instantiate_abstract_llm_trace_repository(self) -> None:
        with pytest.raises(TypeError):
            AbstractLLMTraceRepository()  # type: ignore[abstract]


class TestMethodSignaturesUseDomainModels:
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

    def test_artifact_repo_signatures_use_pydantic_models(self) -> None:
        hints = {
            "create": {"artifact": Artifact, "return": Artifact},
            "list_by_run": {"run_id": str, "return": list[Artifact]},
        }
        for method_name, expected in hints.items():
            method = getattr(AbstractArtifactRepository, method_name)
            annotations = inspect.get_annotations(method)
            for param, expected_type in expected.items():
                assert param in annotations, (
                    f"{method_name} missing annotation for '{param}'"
                )
                assert annotations[param] == expected_type, (
                    f"{method_name}.{param}: expected {expected_type}, got {annotations[param]}"
                )

    def test_llm_trace_repo_signatures_use_pydantic_models(self) -> None:
        hints = {
            "create": {"trace": LLMTrace, "return": LLMTrace},
            "list_recent": {"limit": int, "return": list[LLMTrace]},
            "list_by_run": {"run_id": str, "return": list[LLMTrace]},
        }
        for method_name, expected in hints.items():
            method = getattr(AbstractLLMTraceRepository, method_name)
            annotations = inspect.get_annotations(method)
            for param, expected_type in expected.items():
                assert param in annotations, (
                    f"{method_name} missing annotation for '{param}'"
                )
                assert annotations[param] == expected_type, (
                    f"{method_name}.{param}: expected {expected_type}, got {annotations[param]}"
                )


class TestFkPragmaEnablesForeignKeys:
    def test_fk_pragma_returns_1_after_enable(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        enable_sqlite_fk_pragma(engine)
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
            assert result == 1


# ---------------------------------------------------------------------------
# EC Tests
# ---------------------------------------------------------------------------


class TestIncompleteSubclassRaisesTypeerror:
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


class TestDirectInstantiationRaisesTypeerror:
    def test_direct_instantiation_error_mentions_abstract_methods(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            AbstractRunRepository()  # type: ignore[abstract]

        error_msg = str(exc_info.value)
        # Python's TypeError for ABCs mentions "abstract" and the method names
        assert "abstract" in error_msg.lower()
        for method in ("create", "get", "update_status", "update_projection"):
            assert method in error_msg, f"Expected '{method}' in error: {error_msg}"
