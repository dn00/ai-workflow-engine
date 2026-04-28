.PHONY: test lint format demo eval export-bundle install

test:
	uv run --extra dev pytest -q

lint:
	uv run --extra dev ruff check .
	uv run --extra dev ruff format --check .

format:
	uv run --extra dev ruff format .
	uv run --extra dev ruff check --fix .

eval:
	uv run --extra dev python scripts/run_evals.py

install:
	uv sync --extra dev

demo:
	@mkdir -p data
	@echo "============================================="
	@echo "  AI Workflow Engine — Demo"
	@echo "============================================="
	@echo ""
	@echo "  Open http://127.0.0.1:8000/ui/intake"
	@echo "  API docs: http://127.0.0.1:8000/docs"
	@echo "  Press Ctrl+C to stop"
	@echo ""
	LLM_ADAPTER=cli uvicorn app.main:app --host 127.0.0.1 --port 8000

export-bundle:
	python scripts/export_bundle.py $(RUN_ID)
