from __future__ import annotations

from .circuit_breaker import CircuitBreaker, CircuitState
from .llm_fallback import (
    AllProvidersFailed,
    FallbackLLMClient,
    OllamaClient,
    ProviderSpec,
    adapt_prompt_for_small_model,
    build_default_fallback_llm,
    is_transient_error,
)
from .orchestrator import evaluate_with_fallback
from .parsing import ParseOutcome, ParsingExhausted, parse_recommendation
from .rules import evaluate_by_rules, is_tool_allowed_in_mode
from .tool_fallback import LastKnownCache, ResilientToolExecutor
from .trace import FallbackTrace, LEVEL_MODEL, LEVEL_PARSING, LEVEL_RULES, LEVEL_TOOL, fallback_trace, record

__all__ = [
    "CircuitBreaker", "CircuitState",
    "FallbackLLMClient", "ProviderSpec", "OllamaClient", "AllProvidersFailed",
    "adapt_prompt_for_small_model", "build_default_fallback_llm", "is_transient_error",
    "ResilientToolExecutor", "LastKnownCache",
    "parse_recommendation", "ParseOutcome", "ParsingExhausted",
    "evaluate_by_rules", "is_tool_allowed_in_mode",
    "evaluate_with_fallback",
    "FallbackTrace", "fallback_trace", "record",
    "LEVEL_MODEL", "LEVEL_TOOL", "LEVEL_PARSING", "LEVEL_RULES",
]
