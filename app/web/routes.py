"""Web UI routes — Jinja2 template rendering for the 5 spec §26 screens.

Batch 01: intake screen (GET + POST /ui/intake).
Batch 02: run detail (GET /ui/runs/{run_id}), review (POST), replay (POST).
"""

import json
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.enums import ReviewDecision, RunMode
from app.core.runners.base import RunnerError

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@router.get("/intake", response_class=HTMLResponse)
async def intake_form(request: Request):
    """Render the intake form (spec §26 screen 1)."""
    return templates.TemplateResponse(request, "intake.html")


@router.post("/intake")
async def intake_submit(
    request: Request,
    input_text: str = Form(""),
    mode: str = Form("live"),
):
    """Process intake form submission — create run and redirect to detail."""
    runner = request.app.state.runner
    run_mode = RunMode(mode)
    try:
        result = runner.start_run(input_text, run_mode)
    except RunnerError as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"error_message": str(exc)},
            status_code=200,
        )
    except Exception:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"error_message": "An error occurred while processing your request"},
            status_code=500,
        )
    run_id = result.run.run_id
    return RedirectResponse(url=f"/ui/runs/{run_id}", status_code=303)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(request: Request, run_id: str):
    """Render run detail page (spec §26 screens 2, 3, 4)."""
    run_repo = request.app.state.run_repo
    event_repo = request.app.state.event_repo
    receipt_repo = request.app.state.receipt_repo
    review_repo = request.app.state.review_repo

    run = run_repo.get(run_id)
    if run is None:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"error_message": f"Run not found: {run_id}"},
            status_code=404,
        )

    events = event_repo.list_by_run(run_id)
    receipt = receipt_repo.get_by_run(run_id)
    review = review_repo.get_by_run(run_id)

    return templates.TemplateResponse(
        request,
        "run_detail.html",
        context={
            "run": run,
            "events": events,
            "receipt": receipt,
            "review": review,
        },
    )


@router.post("/runs/{run_id}/review")
async def review_submit(
    request: Request,
    run_id: str,
    decision: str = Form(...),
):
    """Process review decision (spec §26 screen 4)."""
    runner = request.app.state.runner
    try:
        review_decision = ReviewDecision(decision)
        runner.submit_review(run_id, review_decision)
    except RunnerError as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"error_message": str(exc)},
            status_code=200,
        )
    return RedirectResponse(url=f"/ui/runs/{run_id}", status_code=303)


@router.post("/runs/{run_id}/replay", response_class=HTMLResponse)
async def replay_submit(request: Request, run_id: str):
    """Trigger replay and render result (spec §26 screen 5)."""
    runner = request.app.state.runner
    try:
        result = runner.replay_run(run_id)
    except RunnerError as exc:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"error_message": str(exc)},
            status_code=200,
        )

    # Format projections as JSON for display
    replayed_json = None
    if result.replayed_projection is not None:
        replayed_json = json.dumps(result.replayed_projection.model_dump(), indent=2, default=str)

    stored_json = None
    if result.stored_projection is not None:
        stored_json = json.dumps(result.stored_projection, indent=2, default=str)

    return templates.TemplateResponse(
        request,
        "replay_result.html",
        context={
            "result": result,
            "replayed_json": replayed_json,
            "stored_json": stored_json,
        },
    )
