IMAGE  := siftguard
TAG    := latest
PORT   := 8080
CONTAINER := siftguard-demo

.PHONY: build demo demo-stop test lint type lock clean

## build — compile linux/amd64 image (matches SIFT Workstation + CI runners)
build:
	docker buildx build \
		--platform linux/amd64 \
		--load \
		-t $(IMAGE):$(TAG) \
		.

## demo — build image, launch dashboard on http://localhost:8080 (no API calls)
demo: build
	@docker rm -f $(CONTAINER) 2>/dev/null || true
	docker run -d \
		--name $(CONTAINER) \
		--platform linux/amd64 \
		-p $(PORT):$(PORT) \
		$(IMAGE):$(TAG)
	@echo "Waiting for dashboard…"
	@timeout 60 sh -c \
		'until curl -sf http://localhost:$(PORT)/ >/dev/null; do sleep 2; done' \
		&& echo "✓  Dashboard ready → http://localhost:$(PORT)"

## demo-stop — stop and remove the demo container
demo-stop:
	docker rm -f $(CONTAINER) 2>/dev/null || true

## test — run full pytest suite (no API calls, no live agent runs)
test:
	python -m pytest tests/ -v --tb=short -p no:warnings \
		--ignore=tests/infra/test_makefile_exists.py

## lint — ruff check + format check
lint:
	python -m ruff check src/ tests/
	python -m ruff format --check src/ tests/

## type — mypy strict
type:
	python -m mypy src/ --ignore-missing-imports

## lock — pin requirements (requires pip-tools: pip install pip-tools)
lock:
	@command -v pip-compile >/dev/null 2>&1 || pip install pip-tools
	pip-compile --strip-extras --output-file=requirements.txt pyproject.toml
	pip-compile --strip-extras --extra=dev --output-file=requirements-dev.txt pyproject.toml

## clean — remove image, containers, caches
clean: demo-stop
	docker rmi -f $(IMAGE):$(TAG) 2>/dev/null || true
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache  -exec rm -rf {} + 2>/dev/null || true
