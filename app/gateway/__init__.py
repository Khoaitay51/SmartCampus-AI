from __future__ import annotations
 
from .client import GatewayClient, GatewayError
from .db import AgentStateDB, get_db
from .llm_client import AnthropicLLMClient, LLMClient
from .rag import RagBudgetExceeded, RagCallBudget, RagClient, execute_rag_tool
from .recommendations import ExecutionResult, RecommendationPayload, RecommendationsClient, ToolCall
from .rooms import RoomsClient
 
__all__ = [
    "Gateway",
    "GatewayClient",
    "GatewayError",
    "RoomsClient",
    "RagClient",
    "RagCallBudget",
    "RagBudgetExceeded",
    "execute_rag_tool",
    "RecommendationsClient",
    "RecommendationPayload",
    "ExecutionResult",
    "ToolCall",
    "LLMClient",
    "AnthropicLLMClient",
    "AgentStateDB",
    "get_db",
]
 
 
class Gateway:
    """Facade tiện dùng — 1 GatewayClient (1 connection pool) dùng chung cho
    rooms / rag / recommendations. Tạo 1 instance dùng suốt vòng đời agent process.
    """
 
    def __init__(self, base_url: str | None = None) -> None:
        self._client = GatewayClient(base_url=base_url)
        self.rooms = RoomsClient(self._client)
        self.rag = RagClient(self._client)
        self.recommendations = RecommendationsClient(self._client)
        self.llm = LLMClient()
 
    async def __aenter__(self) -> "Gateway":
        await self._client.__aenter__()
        return self
 
    async def __aexit__(self, *exc: object) -> None:
        await self._client.__aexit__(*exc)
 