.PHONY: test bench-test002-all demo

test:
	python3 -m pytest --tb=short -q

.PHONY: bench-test001-all bench-test002-all bench-all
bench-test001-all:
	@for a in native langgraph openai-fc gemini claudecode; do echo "=== TEST-001: $$a ===" && python -m siftguard.eval.run_experiment --agent $$a --case TEST-001 --gt-version 1.1.0 || exit 1; done
	@echo "=== TEST-001: all agents complete ==="

bench-test002-all:
	@for a in native langgraph openai-fc gemini claudecode; do echo "=== TEST-002: $$a ===" && python -m siftguard.eval.run_experiment --agent $$a --case TEST-002 --gt-version 1.1.0 || exit 1; done
	@echo "=== TEST-002: all agents complete ==="

bench-all: bench-test001-all bench-test002-all

demo:
	uvicorn siftguard.dashboard.app:app --host 0.0.0.0 --port 8080 --reload
