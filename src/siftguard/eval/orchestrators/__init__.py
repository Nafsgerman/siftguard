"""Orchestrator registry — keep alphabetical."""
from siftguard.eval.orchestrators.base import BaseOrchestrator, OrchestratorResult
from siftguard.eval.orchestrators.claude_code_adapter import ClaudeCodeAdapter
from siftguard.eval.orchestrators.gemini_adapter import GeminiAdapter
from siftguard.eval.orchestrators.langgraph_adapter import LangGraphAdapter
from siftguard.eval.orchestrators.native_loop import NativeLoopAdapter
from siftguard.eval.orchestrators.openai_fc_adapter import OpenAIFunctionCallingAdapter

REGISTRY: dict[str, type[BaseOrchestrator]] = {
    "siftguard-claudecode": ClaudeCodeAdapter,
    "siftguard-gemini3pro": GeminiAdapter,
    "siftguard-langgraph": LangGraphAdapter,
    "siftguard-native": NativeLoopAdapter,
    "siftguard-openai-fc": OpenAIFunctionCallingAdapter,
}

__all__ = [
    "BaseOrchestrator",
    "OrchestratorResult",
    "ClaudeCodeAdapter",
    "GeminiAdapter",
    "LangGraphAdapter",
    "NativeLoopAdapter",
    "OpenAIFunctionCallingAdapter",
    "REGISTRY",
]