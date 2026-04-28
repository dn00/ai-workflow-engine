"""Route-level tests for read-only observability endpoints."""

from starlette.testclient import TestClient

from app.main import create_app


def test_list_llm_traces_returns_recent_trace() -> None:
    app = create_app(db_url="sqlite:///:memory:")
    with TestClient(app) as client:
        run_resp = client.post(
            "/runs/",
            json={"input_text": "Hello IT", "mode": "live"},
        )
        run_id = run_resp.json()["run"]["run_id"]

        resp = client.get("/observability/llm-traces")

    assert resp.status_code == 200
    traces = resp.json()["traces"]
    assert len(traces) == 1
    assert traces[0]["run_id"] == run_id
    assert traces[0]["workflow_type"] == "access_request"
    assert traces[0]["parse_success"] is True
    assert traces[0]["policy_status"] == "approved"


def test_list_llm_traces_by_run_returns_trace_for_existing_run() -> None:
    app = create_app(db_url="sqlite:///:memory:")
    with TestClient(app) as client:
        run_resp = client.post(
            "/runs/",
            json={"input_text": "Hello IT", "mode": "live"},
        )
        run_id = run_resp.json()["run"]["run_id"]

        resp = client.get(f"/observability/llm-traces/{run_id}")

    assert resp.status_code == 200
    traces = resp.json()["traces"]
    assert len(traces) == 1
    assert traces[0]["run_id"] == run_id


def test_list_llm_traces_by_run_unknown_returns_404() -> None:
    app = create_app(db_url="sqlite:///:memory:")
    with TestClient(app) as client:
        resp = client.get("/observability/llm-traces/missing-run")

    assert resp.status_code == 404
