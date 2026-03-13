"""Runner layer — abstract interface, result model, error type, and LocalRunner."""

from app.core.runners.base import AbstractRunner, RunnerError
from app.core.runners.local_runner import LocalRunner
from app.core.runners.models import RunResult

__all__ = ["AbstractRunner", "LocalRunner", "RunResult", "RunnerError"]
