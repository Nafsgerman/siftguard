# SIFTGuard developer Makefile — single entry point for build, demo, test, lint.
# `make demo` is the reviewer-grade 5-minute cold-clone gate.

SHELL := /bin/bash
IMAGE := siftguard:demo
CONTAINER := siftguard-demo
PORT := 8080
PLATFORM := linux/amd64
VOLATILITY3_REF ?= develop

.PHONY: help build demo demo-logs demo-stop test lint type lock clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

build: ## Build SIFTGuard image for linux/amd64
	docker buildx build --platform=$(PLATFORM) --load \
		--build-arg VOLATILITY3_REF=$(VOLATILITY3_REF) \
		-t $(IMAGE) .

demo: build ## Cold-clone demo — build + launch dashboard at http://localhost:8080
	@docker rm -f $(CONTAINER) >/dev/null 2>&1 || true
	docker run -d --name $(CONTAINER) -p $(PORT):8080 $(IMAGE)
	@echo "Waiting for dashboard..."
	@for i in $$(seq 1 30); do \
		if curl -fsS http://localhost:$(PORT)/ >/dev/null 2>&1; then \
			echo "✓ Dashboard live: http://localhost:$(PORT)"; exit 0; \
		fi; sleep 1; \
	done; \
	echo "✗ Dashboard failed within 30s"; docker logs $(CONTAINER); exit 1

demo-logs: ## Tail demo container logs
	docker logs -f $(CONTAINER)

demo-stop: ## Stop + remove demo container
	docker rm -f $(CONTAINER) >/dev/null 2>&1 || true

test: ## Run pytest suite
	python3 -m pytest -q

lint: ## ruff check + format check
	python3 -m ruff check src/ tests/
	python3 -m ruff format --check src/ tests/

type: ## mypy (non-blocking until T20)
	python3 -m mypy src/ || true

lock: ## Regenerate requirements*.txt from pyproject.toml
	pip-compile --strip-extras --output-file=requirements.txt pyproject.toml
	pip-compile --strip-extras --extra=dev --output-file=requirements-dev.txt pyproject.toml

clean: ## Wipe caches + build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info