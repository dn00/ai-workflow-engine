"""FastAPI dependency functions for the /runs API."""

from fastapi import Request

from app.core.runners.local_runner import LocalRunner
from app.db.repositories.base import (
    AbstractArtifactRepository,
    AbstractEventRepository,
    AbstractLLMTraceRepository,
    AbstractReceiptRepository,
    AbstractRetrievalTraceRepository,
    AbstractReviewRepository,
    AbstractRunRepository,
)


def get_runner(request: Request) -> LocalRunner:
    """Retrieve the runner instance from app state."""
    return request.app.state.runner


def get_run_repo(request: Request) -> AbstractRunRepository:
    """Retrieve the run repository from app state."""
    return request.app.state.run_repo


def get_event_repo(request: Request) -> AbstractEventRepository:
    """Retrieve the event repository from app state."""
    return request.app.state.event_repo


def get_receipt_repo(request: Request) -> AbstractReceiptRepository:
    """Retrieve the receipt repository from app state."""
    return request.app.state.receipt_repo


def get_review_repo(request: Request) -> AbstractReviewRepository:
    """Retrieve the review repository from app state."""
    return request.app.state.review_repo


def get_artifact_repo(request: Request) -> AbstractArtifactRepository:
    """Retrieve the artifact repository from app state."""
    return request.app.state.artifact_repo


def get_llm_trace_repo(request: Request) -> AbstractLLMTraceRepository:
    """Retrieve the LLM trace repository from app state."""
    return request.app.state.llm_trace_repo


def get_retrieval_trace_repo(request: Request) -> AbstractRetrievalTraceRepository:
    """Retrieve the retrieval trace repository from app state."""
    return request.app.state.retrieval_trace_repo
