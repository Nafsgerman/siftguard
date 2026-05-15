.PHONY: test bench-test002-all demo

test:
	python3 -m pytest --tb=short -q

bench-test002-all:
	@echo "=== TEST-002: langgraph ===" && python3 -m siftguard.eval.run_experiment --orchestrator siftguard-langgraph --case TEST-002
	@echo "=== TEST-002: openai-fc ===" && python3 -m siftguard.eval.run_experiment --orchestrator siftguard-openai-fc --case TEST-002
	@echo "=== TEST-002: gemini ===" && python3 -m siftguard.eval.run_experiment --orchestrator siftguard-gemini --case TEST-002
	@echo "=== TEST-002: claudecode ===" && python3 -m siftguard.eval.run_experiment --orchestrator siftguard-claudecode --case TEST-002
	@echo "=== TEST-002: all complete ==="

demo:
	uvicorn siftguard.dashboard.app:app --host 0.0.0.0 --port 8080 --reload
