UV ?= uv
CODE_PATHS := src/privacy_service tests

.PHONY: help install dev test lint format type-check check pre-commit-install pre-commit

help:
	@echo "Privacy Service - Makefile targets (using uv)"
	@echo "  make install            Sync environment and install package in editable mode"
	@echo "  make dev                Sync dev environment (uv group: dev)"
	@echo "  make test               Run test suite with pytest"
	@echo "  make lint               Run ruff linting"
	@echo "  make format             Run black code formatter"
	@echo "  make type-check         Run mypy type checker"
	@echo "  make check              Run lint, type-check, and tests"
	@echo "  make pre-commit-install Install pre-commit hooks"
	@echo "  make pre-commit         Run pre-commit on all files"

install:
	$(UV) sync
	$(UV) run python -m pip install -e .

dev:
	$(UV) sync --group dev
	$(UV) run python -m pip install -e .

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check $(CODE_PATHS)

format:
	$(UV) run ruff format $(CODE_PATHS)

type-check:
	$(UV) run mypy --follow-untyped-imports src/privacy_service

check: lint type-check test

pre-commit-install:
	$(UV) run pre-commit install

pre-commit:
	$(UV) run pre-commit run --all-files


