"""LocalRunner — synchronous orchestrator for workflow runs.

Implements start_run (this module), submit_review and replay_run
(added by Batch 03). Emits events, enforces state machine, delegates
to workflow modules via the registry.
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.enums import ActorType, EventType, ReviewDecision, RunMode, RunStatus
from app.core.models import Event, ReviewTask, Run, VersionInfo
from app.core.projections.models import RunProjection
from app.core.projections.reducer import reduce_events
from app.core.replay.engine import replay_run as _replay_run_engine
from app.core.replay.models import ReplayResult
from app.db.repositories.base import (
    AbstractEventRepository,
    AbstractReviewRepository,
    AbstractRunRepository,
)
from app.effects.base import AbstractEffectAdapter, check_effect_preconditions
from app.workflows.registry import get_workflow

from .base import AbstractRunner, RunnerError
from .models import RunResult


class LocalRunner(AbstractRunner):
    """Synchronous runner that orchestrates workflow runs locally."""

    def __init__(
        self,
        run_repo: AbstractRunRepository,
        event_repo: AbstractEventRepository,
        review_repo: AbstractReviewRepository,
        effect_adapter: AbstractEffectAdapter,
    ) -> None:
        self._run_repo = run_repo
        self._event_repo = event_repo
        self._review_repo = review_repo
        self._effect_adapter = effect_adapter

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _emit(
        self,
        run_id: str,
        seq: int,
        event_type: EventType,
        actor_type: ActorType,
        payload: dict,
        version_info: VersionInfo,
        idempotency_key: str | None = None,
    ) -> Event:
        """Create and persist an event."""
        event = Event(
            run_id=run_id,
            seq=seq,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            version_info=version_info,
            payload=payload,
            actor_type=actor_type,
            idempotency_key=idempotency_key,
        )
        return self._event_repo.append(event)

    def _update_status(self, run_id: str, status: RunStatus) -> None:
        """Update run status in the repository."""
        self._run_repo.update_status(run_id, status, datetime.now(timezone.utc))

    def _build_projection(self, run_id: str) -> RunProjection:
        """Build projection from stored events."""
        events = self._event_repo.list_by_run(run_id)
        return reduce_events(events)

    def _update_projection(self, run_id: str) -> RunProjection:
        """Build projection and persist it on the run."""
        projection = self._build_projection(run_id)
        self._run_repo.update_projection(
            run_id, projection.model_dump(), datetime.now(timezone.utc)
        )
        return projection

    def _run_result(
        self, run_id: str, review_task: ReviewTask | None = None
    ) -> RunResult:
        """Build and return a RunResult with fresh projection."""
        run = self._run_repo.get(run_id)
        projection = self._update_projection(run_id)
        return RunResult(run=run, projection=projection, review_task=review_task)

    def _run_effect_phase(
        self,
        run_id: str,
        seq: int,
        version_info: VersionInfo,
        mode: RunMode,
    ) -> int:
        """Execute the effect phase (LIVE mode only). Returns next seq."""
        if mode != RunMode.LIVE:
            return seq

        idempotency_key = str(uuid4())

        # Emit effect.requested
        self._emit(
            run_id, seq, EventType.EFFECT_REQUESTED,
            ActorType.RUNNER, {}, version_info,
            idempotency_key=idempotency_key,
        )
        self._update_status(run_id, RunStatus.EFFECT_PENDING)
        seq += 1

        # Check preconditions and execute
        check_effect_preconditions(RunStatus.APPROVED, mode, idempotency_key)
        receipt = self._effect_adapter.execute(run_id, idempotency_key)

        # Emit effect.simulated
        self._emit(
            run_id, seq, EventType.EFFECT_SIMULATED,
            ActorType.SYSTEM, receipt, version_info,
        )
        self._update_status(run_id, RunStatus.EFFECT_APPLIED)
        seq += 1

        return seq

    # ------------------------------------------------------------------
    # Public commands
    # ------------------------------------------------------------------

    def start_run(self, input_text: str, mode: RunMode) -> RunResult:
        """Orchestrate a new workflow run from raw input."""
        # Guard: REPLAY mode not allowed via start_run
        if mode == RunMode.REPLAY:
            raise RunnerError(
                "Cannot use REPLAY mode with start_run. Use replay_run instead."
            )

        # Create the run
        run = Run(mode=mode)
        run = self._run_repo.create(run)
        run_id = run.run_id
        version_info = VersionInfo()
        seq = 1

        # Resolve workflow module
        try:
            wf = get_workflow(run.workflow_type)
        except ValueError as exc:
            raise RunnerError(str(exc)) from exc

        # 1. run.received
        self._emit(
            run_id, seq, EventType.RUN_RECEIVED,
            ActorType.RUNNER, {}, version_info,
        )
        seq += 1

        # 2. Parse proposal
        parse_result = wf.parse_proposal(input_text)
        if not parse_result.success:
            # proposal.parse_failed → exit
            self._emit(
                run_id, seq, EventType.PROPOSAL_PARSE_FAILED,
                ActorType.SYSTEM,
                {"error": parse_result.error},
                version_info,
            )
            self._update_status(run_id, RunStatus.PROPOSAL_INVALID)
            return self._run_result(run_id)

        # 3. proposal.generated
        self._emit(
            run_id, seq, EventType.PROPOSAL_GENERATED,
            ActorType.SYSTEM,
            {"proposal": parse_result.proposal if isinstance(parse_result.proposal, dict) else {}},
            version_info,
        )
        seq += 1

        # 4. Normalize + validate
        normalized = wf.normalize_proposal(parse_result.proposal)
        validation_result = wf.validate_proposal(parse_result.proposal, normalized)

        if not validation_result.is_valid:
            # validation.failed → exit
            self._emit(
                run_id, seq, EventType.VALIDATION_FAILED,
                ActorType.SYSTEM,
                {"errors": validation_result.errors},
                version_info,
            )
            self._update_status(run_id, RunStatus.PROPOSAL_INVALID)
            return self._run_result(run_id)

        # 5. validation.completed
        self._emit(
            run_id, seq, EventType.VALIDATION_COMPLETED,
            ActorType.SYSTEM, {}, version_info,
        )
        self._update_status(run_id, RunStatus.VALIDATED)
        seq += 1

        # 6. Evaluate policy
        decision = wf.evaluate_policy(
            parse_result.proposal,
            normalized,
            validation_result,
            policy_version=version_info.policy_version,
        )

        # 7. decision.committed
        self._emit(
            run_id, seq, EventType.DECISION_COMMITTED,
            ActorType.SYSTEM,
            {"status": decision.status, "reason_codes": decision.reason_codes},
            version_info,
        )
        seq += 1

        # Branch on decision status
        if decision.status == "approved":
            self._update_status(run_id, RunStatus.APPROVED)

            # Effect phase (skipped in DRY_RUN)
            seq = self._run_effect_phase(run_id, seq, version_info, mode)

            # run.completed
            self._emit(
                run_id, seq, EventType.RUN_COMPLETED,
                ActorType.RUNNER, {}, version_info,
            )
            self._update_status(run_id, RunStatus.COMPLETED)
            return self._run_result(run_id)

        elif decision.status == "review_required":
            self._update_status(run_id, RunStatus.REVIEW_REQUIRED)

            # review.requested
            self._emit(
                run_id, seq, EventType.REVIEW_REQUESTED,
                ActorType.RUNNER, {}, version_info,
            )

            # Create review task
            review_task = ReviewTask(run_id=run_id)
            review_task = self._review_repo.create(review_task)
            return self._run_result(run_id, review_task=review_task)

        else:
            # rejected → run.completed (no effects)
            self._update_status(run_id, RunStatus.REJECTED)

            self._emit(
                run_id, seq, EventType.RUN_COMPLETED,
                ActorType.RUNNER, {}, version_info,
            )
            self._update_status(run_id, RunStatus.COMPLETED)
            return self._run_result(run_id)

    def submit_review(self, run_id: str, decision: ReviewDecision) -> RunResult:
        """Submit a review decision for a run in review_required status."""
        # Load and validate run
        run = self._run_repo.get(run_id)
        if run is None:
            raise RunnerError(f"Run not found: {run_id}")
        if run.status != RunStatus.REVIEW_REQUIRED:
            raise RunnerError(
                f"Run {run_id} is not in review_required status (current: {run.status})"
            )

        # Load review task
        review_task = self._review_repo.get_by_run(run_id)
        version_info = VersionInfo()

        # Determine next seq from existing events
        existing_events = self._event_repo.list_by_run(run_id)
        seq = len(existing_events) + 1

        # Update review decision
        self._review_repo.update_decision(
            review_task.review_id, decision, datetime.now(timezone.utc)
        )

        if decision == ReviewDecision.APPROVE:
            # review.approved
            self._emit(
                run_id, seq, EventType.REVIEW_APPROVED,
                ActorType.REVIEWER,
                {"review_id": review_task.review_id, "decision": decision.value},
                version_info,
            )
            self._update_status(run_id, RunStatus.APPROVED)
            seq += 1

            # Effect phase (skipped in DRY_RUN)
            seq = self._run_effect_phase(run_id, seq, version_info, run.mode)

            # run.completed
            self._emit(
                run_id, seq, EventType.RUN_COMPLETED,
                ActorType.RUNNER, {}, version_info,
            )
            self._update_status(run_id, RunStatus.COMPLETED)

        else:
            # review.rejected
            self._emit(
                run_id, seq, EventType.REVIEW_REJECTED,
                ActorType.REVIEWER,
                {"review_id": review_task.review_id, "decision": decision.value},
                version_info,
            )
            self._update_status(run_id, RunStatus.REJECTED)
            seq += 1

            # run.completed
            self._emit(
                run_id, seq, EventType.RUN_COMPLETED,
                ActorType.RUNNER, {}, version_info,
            )
            self._update_status(run_id, RunStatus.COMPLETED)

        return self._run_result(run_id, review_task=review_task)

    def replay_run(self, run_id: str) -> ReplayResult:
        """Replay a run by re-folding its events and comparing projections."""
        run = self._run_repo.get(run_id)
        if run is None:
            raise RunnerError(f"Run not found: {run_id}")

        events = self._event_repo.list_by_run(run_id)
        stored_projection = run.current_projection
        return _replay_run_engine(run_id, events, stored_projection)
