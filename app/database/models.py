from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, JSON, String, func
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

from app.config.settings import settings

Base = declarative_base()


class AgentExperienceLog(Base):
    __tablename__ = "agent_experience_logs"
    __table_args__ = {"schema": "agent_memory"}

    id = Column(String, primary_key=True)  # event_id
    event_type = Column(String, nullable=False)
    operational_context = Column(JSON, nullable=False)

    # Vector embedding of operational context (default 1024 for Voyage AI / settings)
    context_embedding = Column(Vector(settings.EMBEDDING_DIM))

    # Agent's decision
    agent_reasoning = Column(String, nullable=True)
    recommended_tool = Column(String, nullable=True)

    # RLHF labels (Updated later by human feedback/background worker)
    human_approved = Column(Boolean, nullable=True)
    env_reward = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
