.PHONY: install test lint typecheck check run serve docker docker-run clean

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy

check: lint typecheck test

run:
	python main.py

serve:
	uvicorn app:app --host 0.0.0.0 --port 8000 --reload

docker:
	docker build -t support-ticket-triage .

docker-run:
	docker run --rm -p 8000:8000 -e ANTHROPIC_API_KEY=$${ANTHROPIC_API_KEY} support-ticket-triage

clean:
	rm -rf .ruff_cache .mypy_cache .pytest_cache **/__pycache__ *.egg-info
