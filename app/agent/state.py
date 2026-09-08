from __future__ import annotations
 
from datetime import datetime, timezone
 
from pydantic import BaseModel, Field
 
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload
from app.schemas.recommendation import ToolCallLogEntry

class TrajectoryStep(BaseModel):
    self_ask: str | None = None
    thought: str
    action: str
    action_input: dict
    observation: str

class AgentRunState(BaseModel):
    event: EventPayload
    context: OperationalContext

    trajectory: list[TrajectoryStep] = Field(default_factory=list)
    tool_calls_log: list[ToolCallLogEntry] = Field(default_factory=list)

    reflections: list[str] = Field(default_factory=list)

    round: int = 0
    max_react_step: int = 6
    max_reflect_step: int = 3
    rag_calls_remaining: int = 5

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def render_scratchpad(self) -> str:
        lines = []
        for step in self.trajectory:
            if step.self_ask:
                lines.append(f"Self-Ask: {step.self_ask}")
            lines.append(f"Thought: {step.thought}")
            lines.append(f"Action: {step.action}")
            lines.append(f"Action input: {step.action_input}")
            lines.append(f"Observation: {step.observation}")
        return "\n".join(lines)

    def render_reflections(self) -> str:
        if not self.reflections:
            return "(no prior feedback)"
        return "\n".join(f"- {r}" for r in self.reflections)

    def elapsed_seconds(self) -> float:
        return(datetime.now(timezone.utc) - self.started_at).total_seconds()
