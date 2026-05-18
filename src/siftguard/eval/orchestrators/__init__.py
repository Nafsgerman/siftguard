from siftguard.eval.orchestrators.base import BaseOrchestrator, OrchestratorResult
from siftguard.eval.orchestrators.claude_code_adapter import ClaudeCodeAdapter

try:
    from siftguard.eval.orchestrators.gemini_adapter import GeminiAdapter
except ImportError:
    GeminiAdapter = None

try:
    from siftguard.eval.orchestrators.langgraph_adapter import LangGraphAdapter
except ImportError:
    LangGraphAdapter = None

try:
    from siftguard.eval.orchestrators.native_loop import NativeLoopAdapter
except ImportError:
    NativeLoopAdapter = None

try:
    from siftguard.eval.orchestrators.openai_fc_adapter import OpenAIFunctionCallingAdapter
except ImportError:
    OpenAIFunctionCallingAdapter = None

REGISTRY: dict[str, type[BaseOrchestrator]] = {
    k: v
    for k, v in {
        "siftguard-claudecode": ClaudeCodeAdapter,
        "siftguard-gemini3pro": GeminiAdapter,
        "siftguard-langgraph": LangGraphAdapter,
        "siftguard-native": NativeLoopAdapter,
        "siftguard-openai-fc": OpenAIFunctionCallingAdapter,
    }.items()
    if v is not None
}

__all__ = [
    "REGISTRY",
    "BaseOrchestrator",
    "ClaudeCodeAdapter",
    "GeminiAdapter",
    "LangGraphAdapter",
    "NativeLoopAdapter",
    "OpenAIFunctionCallingAdapter",
    "OrchestratorResult",
]
