# SIFTGuard developer Makefile — single entry point for build, demo, test, lint.
# `make demo` is the reviewer-grade 5-minute cold-clone gate.

SHELL := /bin/bash
IMAGE := siftguard:demo
CONTAINER := siftguard-demo
PORT := 8080
PLATFORM := linux/amd64
VOLATILITY3_REF ?= develop

.PHONY: help build demo demo-logs demo-stop test tool-catalog lint type lock clean

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

# insert after the test target block, before lint:
tool-catalog: ## Regenerate docs/TOOL_CATALOG.md from MCP server definitions
	python3 -m siftguard.release.tool_catalog

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

# ── T21: SBOM + Release ────────────────────────────────────────────────────────

.PHONY: sbom sbom-verify deps-doc

sbom:
	syft . -o spdx-json=sbom.spdx.json -o cyclonedx-json=sbom.cyclonedx.json
	@echo "✓ sbom.spdx.json + sbom.cyclonedx.json generated"

sbom-verify:
	@test -f sbom.spdx.json.bundle || { echo "No bundle — bundles are generated in CI after cosign sign-blob."; exit 1; }
	cosign verify-blob \
		--bundle sbom.spdx.json.bundle \
		--certificate-identity-regexp 'https://github.com/Nafsgerman/siftguard/.github/workflows/release.yml' \
		--certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \
		sbom.spdx.json

deps-doc:
	python3 -c "\
import tomllib, pathlib, datetime; \
data = tomllib.loads(pathlib.Path('pyproject.toml').read_text()); \
deps = data.get('project', {}).get('dependencies', []); \
dev = data.get('project', {}).get('optional-dependencies', {}).get('dev', []); \
lines = ['# SIFTGuard — Direct Dependencies', '', \
'_Auto-generated from \`pyproject.toml\`. **Not the SBOM.** For the full supply-chain inventory see \`sbom.spdx.json\` (SPDX 2.3) or \`sbom.cyclonedx.json\` (CycloneDX 1.5) at repo root._', \
'', f'Generated: {datetime.date.today()}', '', \
'## Runtime', ''] + [f'- \`{d}\`' for d in sorted(deps)] + \
['', '## Dev / CI', ''] + [f'- \`{d}\`' for d in sorted(dev)]; \
pathlib.Path('docs/DEPENDENCIES.md').write_text('\n'.join(lines) + '\n'); \
print('✓ docs/DEPENDENCIES.md written')"
