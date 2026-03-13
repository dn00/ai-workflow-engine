"""Workflow registry for resolving workflow_type to module.

Used by the runner (feature 009) to dispatch workflow processing.
"""

from types import ModuleType

_WORKFLOWS: dict[str, ModuleType] = {}


def register_workflow(workflow_type: str, module: ModuleType) -> None:
    """Register a workflow module for a given workflow_type."""
    _WORKFLOWS[workflow_type] = module


def get_workflow(workflow_type: str) -> ModuleType:
    """Resolve workflow_type to its module. Raises ValueError if unknown."""
    if workflow_type not in _WORKFLOWS:
        raise ValueError(
            f"Unknown workflow type: {workflow_type!r}. "
            f"Registered: {sorted(_WORKFLOWS.keys())}"
        )
    return _WORKFLOWS[workflow_type]


def list_workflow_types() -> list[str]:
    """Return sorted list of registered workflow types."""
    return sorted(_WORKFLOWS.keys())
