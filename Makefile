.PHONY: test lint format demo export-bundle install

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .
	ruff check --fix .

install:
	pip install -e ".[dev]"

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
	uvicorn app.main:app --host 127.0.0.1 --port 8000

export-bundle:
	python scripts/export_bundle.py $(RUN_ID)
