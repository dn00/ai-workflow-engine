"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import runs_router
from app.web import web_router
from app.db.repositories import (
    SQLiteEventRepository,
    SQLiteReceiptRepository,
    SQLiteReviewRepository,
    SQLiteRunRepository,
    enable_sqlite_fk_pragma,
)
from app.db.session import get_engine, get_session_factory, init_db
from app.effects import SimulatedEffectAdapter
from app.llm import AbstractLLMAdapter, MockLLMAdapter


def create_app(
    db_url: str = "sqlite:///data/workflow.db",
    llm_adapter: AbstractLLMAdapter | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(fastapi_app: FastAPI):
        import app.workflows  # noqa: F401 — trigger workflow registration

        engine = get_engine(db_url)
        enable_sqlite_fk_pragma(engine)
        init_db(engine)
        sf = get_session_factory(engine)

        # Create repositories
        run_repo = SQLiteRunRepository(sf)
        event_repo = SQLiteEventRepository(sf)
        review_repo = SQLiteReviewRepository(sf)
        receipt_repo = SQLiteReceiptRepository(sf)

        # Create adapters
        effect_adapter = SimulatedEffectAdapter()
        adapter = llm_adapter or MockLLMAdapter()

        # Create runner
        from app.core.runners.local_runner import LocalRunner

        runner = LocalRunner(
            run_repo=run_repo,
            event_repo=event_repo,
            review_repo=review_repo,
            effect_adapter=effect_adapter,
            llm_adapter=adapter,
            receipt_repo=receipt_repo,
        )

        # Store on app.state for dependency injection
        fastapi_app.state.runner = runner
        fastapi_app.state.run_repo = run_repo
        fastapi_app.state.event_repo = event_repo
        fastapi_app.state.receipt_repo = receipt_repo
        fastapi_app.state.review_repo = review_repo

        yield

    application = FastAPI(title="AI Workflow Engine", lifespan=lifespan)
    application.include_router(runs_router, prefix="/runs", tags=["runs"])
    application.include_router(web_router, prefix="/ui", tags=["web"])
    return application


app = create_app()
