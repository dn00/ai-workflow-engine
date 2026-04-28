"""Workflow registry for resolving workflow_type to workflow module.

Used by the runner (feature 009) to dispatch workflow processing.
"""

from app.workflows.contract import WorkflowModule

_WORKFLOWS: dict[str, WorkflowModule] = {}
_REQUIRED_CALLABLES = (
    "parse_proposal",
    "normalize_proposal",
    "validate_proposal",
    "evaluate_policy",
)


def register_workflow(workflow_type: str, module: WorkflowModule) -> None:
    """Register a workflow module for a given workflow_type."""
    if not workflow_type or not workflow_type.strip():
        raise ValueError("workflow_type must be a non-empty string")
    if workflow_type in _WORKFLOWS:
        raise ValueError(f"Workflow type already registered: {workflow_type!r}")

    missing = [
        name for name in _REQUIRED_CALLABLES
        if not callable(getattr(module, name, None))
    ]
    if missing:
        module_name = getattr(module, "__name__", repr(module))
        raise ValueError(
            f"Workflow module {module_name} missing required callable(s): "
            f"{', '.join(missing)}"
        )

    _WORKFLOWS[workflow_type] = module


def get_workflow(workflow_type: str) -> WorkflowModule:
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
