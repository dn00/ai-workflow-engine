"""FastAPI dependency functions for the /runs API."""

from fastapi import Request

from app.core.runners.local_runner import LocalRunner
from app.db.repositories.base import AbstractEventRepository, AbstractRunRepository


def get_runner(request: Request) -> LocalRunner:
    """Retrieve the runner instance from app state."""
    return request.app.state.runner


def get_run_repo(request: Request) -> AbstractRunRepository:
    """Retrieve the run repository from app state."""
    return request.app.state.run_repo


def get_event_repo(request: Request) -> AbstractEventRepository:
    """Retrieve the event repository from app state."""
    return request.app.state.event_repo
