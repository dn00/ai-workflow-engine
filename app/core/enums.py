"""Core enums for the AI Workflow Engine.

All frozen enums imported by downstream modules. Values match spec exactly.
"""

from enum import StrEnum


class RunStatus(StrEnum):
    """Workflow run statuses (spec §15 — 10 values)."""

    RECEIVED = "received"
    PROPOSAL_GENERATED = "proposal_generated"
    PROPOSAL_INVALID = "proposal_invalid"
    VALIDATED = "validated"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    EFFECT_PENDING = "effect_pending"
    EFFECT_APPLIED = "effect_applied"
    COMPLETED = "completed"


class EventType(StrEnum):
    """Workflow event types (spec §16 — 12 values)."""

    RUN_RECEIVED = "run.received"
    PROPOSAL_GENERATED = "proposal.generated"
    PROPOSAL_PARSE_FAILED = "proposal.parse_failed"
    VALIDATION_COMPLETED = "validation.completed"
    VALIDATION_FAILED = "validation.failed"
    REVIEW_REQUESTED = "review.requested"
    REVIEW_APPROVED = "review.approved"
    REVIEW_REJECTED = "review.rejected"
    DECISION_COMMITTED = "decision.committed"
    EFFECT_REQUESTED = "effect.requested"
    EFFECT_SIMULATED = "effect.simulated"
    RUN_COMPLETED = "run.completed"


class RunMode(StrEnum):
    """Run execution modes (spec §24 — 3 values)."""

    LIVE = "live"
    DRY_RUN = "dry_run"
    REPLAY = "replay"


class ActorType(StrEnum):
    """Actor types for event attribution (spec §16 — 4 values)."""

    SYSTEM = "system"
    LLM = "llm"
    REVIEWER = "reviewer"
    RUNNER = "runner"


class ReasonCode(StrEnum):
    """Policy gate reason codes (spec §20 — 10 values)."""

    MISSING_MANAGER_NAME = "missing_manager_name"
    HIGH_URGENCY = "high_urgency"
    TOO_MANY_SYSTEMS = "too_many_systems"
    UNKNOWN_SYSTEM = "unknown_system"
    FORBIDDEN_SYSTEM = "forbidden_system"
    MALFORMED_DATE = "malformed_date"
    MALFORMED_PROPOSAL = "malformed_proposal"
    AMBIGUOUS_NORMALIZATION = "ambiguous_normalization"
    UNSUPPORTED_REQUEST_TYPE = "unsupported_request_type"
    MANAGER_APPROVAL_UNVERIFIED = "manager_approval_unverified"


class ReviewDecision(StrEnum):
    """Review decisions (spec §21 — 2 values)."""

    APPROVE = "approve"
    REJECT = "reject"


class ReviewStatus(StrEnum):
    """Review task status (spec §13 reviews table — 2 values)."""

    PENDING = "pending"
    COMPLETED = "completed"
