.PHONY: install lint format typecheck test check

install:
	python3 -m pip install -e '.[dev]'

lint:
	python3 -m ruff check .

format:
	python3 -m ruff format .

typecheck:
	python3 -m mypy

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -m pytest

check: lint typecheck test

