"""ReplayBundle model and BundleError (Feature 015, Spec §25, INV-6.2)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.artifacts.models import Artifact
from app.core.models import Event, Run
from app.core.receipts.models import Receipt
from app.observability.llm_traces import LLMTrace


class ReplayBundle(BaseModel):
    """Replay bundle — on-demand snapshot for replay/audit (spec §25, INV-6.2)."""

    bundle_version: str = "1.0"
    exported_at: datetime
    run: Run
    events: list[Event]
    receipt: Receipt | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    llm_traces: list[LLMTrace] = Field(default_factory=list)
    projection: dict | None = None


class BundleError(Exception):
    """Raised when bundle assembly fails."""
