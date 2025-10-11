.PHONY: dev test lint

dev:
	uvicorn src.main:app --reload --port 8000

test:
	pytest -q

lint:
	black .
	flake8
