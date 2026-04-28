"""Read-only observability endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.dependencies import get_llm_trace_repo, get_run_repo
from app.api.schemas.observability import LLMTraceListResponse, LLMTraceResponse
from app.db.repositories.base import AbstractLLMTraceRepository, AbstractRunRepository
from app.observability.llm_traces import LLMTrace

router = APIRouter()


def _serialize_trace(trace: LLMTrace) -> LLMTraceResponse:
    return LLMTraceResponse(**trace.model_dump())


@router.get("/llm-traces", response_model=LLMTraceListResponse)
def list_llm_traces(
    limit: int = Query(default=100, ge=1, le=500),
    llm_trace_repo: AbstractLLMTraceRepository = Depends(get_llm_trace_repo),
):
    """List recent LLM traces."""
    traces = llm_trace_repo.list_recent(limit=limit)
    return LLMTraceListResponse(traces=[_serialize_trace(trace) for trace in traces])


@router.get("/llm-traces/{run_id}", response_model=LLMTraceListResponse)
def list_llm_traces_by_run(
    run_id: str,
    run_repo: AbstractRunRepository = Depends(get_run_repo),
    llm_trace_repo: AbstractLLMTraceRepository = Depends(get_llm_trace_repo),
):
    """List LLM traces for one run."""
    run = run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    traces = llm_trace_repo.list_by_run(run_id)
    return LLMTraceListResponse(traces=[_serialize_trace(trace) for trace in traces])
