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
	@echo "Demo not yet implemented. Run 'make install' first, then 'uvicorn app.main:app'."

export-bundle:
	@echo "Bundle export not yet implemented. Usage: make export-bundle RUN_ID=<id>"
