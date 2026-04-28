"""Protocol for workflow modules consumed by the runner.

The current workflows are module-based. This protocol makes that contract
explicit without forcing a class hierarchy or changing existing modules.
"""

from typing import Any, Protocol


class WorkflowModule(Protocol):
    """Function-based workflow module contract used by LocalRunner."""

    def parse_proposal(self, raw_response: str) -> Any: ...

    def normalize_proposal(self, proposal: Any) -> Any: ...

    def validate_proposal(self, proposal: Any, normalized: Any) -> Any: ...

    def evaluate_policy(
        self,
        proposal: Any,
        normalized: Any,
        validation_result: Any,
        policy_version: str = "1.0",
    ) -> Any: ...
