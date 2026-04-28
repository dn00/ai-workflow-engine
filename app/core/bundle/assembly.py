"""Bundle assembly logic (Feature 015, Spec §25, INV-6.2)."""

from datetime import datetime, timezone

from app.core.bundle.models import BundleError, ReplayBundle
from app.db.repositories.base import (
    AbstractArtifactRepository,
    AbstractEventRepository,
    AbstractLLMTraceRepository,
    AbstractReceiptRepository,
    AbstractRetrievalTraceRepository,
    AbstractRunRepository,
)


def assemble_bundle(
    run_id: str,
    run_repo: AbstractRunRepository,
    event_repo: AbstractEventRepository,
    receipt_repo: AbstractReceiptRepository,
    artifact_repo: AbstractArtifactRepository | None = None,
    llm_trace_repo: AbstractLLMTraceRepository | None = None,
    retrieval_trace_repo: AbstractRetrievalTraceRepository | None = None,
) -> ReplayBundle:
    """Assemble a replay bundle from DB state (INV-6.2)."""
    run = run_repo.get(run_id)
    if run is None:
        raise BundleError(f"Run not found: {run_id}")

    events = event_repo.list_by_run(run_id)
    if not events:
        raise BundleError(f"No events found for run: {run_id}")

    receipt = receipt_repo.get_by_run(run_id)
    artifacts = artifact_repo.list_by_run(run_id) if artifact_repo else []
    llm_traces = llm_trace_repo.list_by_run(run_id) if llm_trace_repo else []
    retrieval_traces = (
        retrieval_trace_repo.list_by_run(run_id) if retrieval_trace_repo else []
    )

    return ReplayBundle(
        exported_at=datetime.now(timezone.utc),
        run=run,
        events=events,
        receipt=receipt,
        artifacts=artifacts,
        llm_traces=llm_traces,
        retrieval_traces=retrieval_traces,
        projection=run.current_projection,
    )
