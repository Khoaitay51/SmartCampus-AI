from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String
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

    # Fallback tracking
    is_fallback = Column(Boolean, nullable=False, default=False, index=True)
    fallback_levels = Column(JSON, nullable=True)

    # RLHF labels (Updated later by human feedback/background worker)
    human_approved = Column(Boolean, nullable=True)
    env_reward = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AgentEnvironmentSnapshot(Base):
    __tablename__ = "environment_snapshots"
    __table_args__ = {"schema": "agent_memory"}

    id = Column(String, primary_key=True)
    event_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    room_id = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, default="edge.query_tool.get_environment")
    since = Column(DateTime(timezone=True), nullable=True)
    row_count = Column(Integer, nullable=False, default=0)
    environment_context = Column(JSON, nullable=False)
    environment_text = Column(String, nullable=False)
    environment_embedding = Column(Vector(settings.EMBEDDING_DIM))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AgentDecisionLog(Base):
    __tablename__ = "agent_decision_logs"
    __table_args__ = {"schema": "agent_memory"}

    id = Column(String, primary_key=True)
    event_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    room_id = Column(String, nullable=False, index=True)
    agent_response = Column(JSON, nullable=False)
    response_text = Column(String, nullable=False)
    response_embedding = Column(Vector(settings.EMBEDDING_DIM))
    analysis = Column(String, nullable=True)
    recommended_tool = Column(String, nullable=True, index=True)
    skip = Column(Boolean, nullable=False, default=False, index=True)
    is_fallback = Column(Boolean, nullable=False, default=False, index=True)
    fallback_levels = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
