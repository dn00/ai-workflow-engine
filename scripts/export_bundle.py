#!/usr/bin/env python3
"""Export a replay bundle to JSON file."""
import json
import os
import sys

from app.core.bundle import BundleError, assemble_bundle
from app.db.repositories import (
    SQLiteEventRepository,
    SQLiteReceiptRepository,
    SQLiteRunRepository,
    enable_sqlite_fk_pragma,
)
from app.db.session import get_engine, get_session_factory


def export_bundle(run_id: str, db_url: str = "sqlite:///data/workflow.db") -> str:
    """Export bundle and return output path."""
    engine = get_engine(db_url)
    enable_sqlite_fk_pragma(engine)
    sf = get_session_factory(engine)
    run_repo = SQLiteRunRepository(sf)
    event_repo = SQLiteEventRepository(sf)
    receipt_repo = SQLiteReceiptRepository(sf)
    bundle = assemble_bundle(run_id, run_repo, event_repo, receipt_repo)
    out_path = f"bundles/{run_id}.json"
    os.makedirs("bundles", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(bundle.model_dump(mode="json"), f, indent=2, default=str)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_bundle.py <RUN_ID>", file=sys.stderr)
        sys.exit(1)
    run_id = sys.argv[1]
    db_url = os.environ.get("DB_URL", "sqlite:///data/workflow.db")
    try:
        path = export_bundle(run_id, db_url)
        print(f"Bundle exported: {path}")
    except BundleError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
