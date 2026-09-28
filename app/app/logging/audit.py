from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from app.config.settings import settings
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse

# mỗi khi /evaluate xử lý xong, ghi 1 file JSON audit gồm: input event + output response
# đc ghi trước khi trả response về gateway
logger = logging.getLogger(__name__)


def _output_path(event_id: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(settings.AUDIT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{ts}_{event_id}.json"


def save_audit_record(event: EventPayload, response: AgentResponse) -> Path | None:
    """Ghi audit record ra file JSON (đồng bộ, dùng tại /evaluate hoặc demo script)."""
    record = {
        "event": json.loads(event.model_dump_json()),
        "response": json.loads(response.model_dump_json()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    path = _output_path(str(event.event_id))
    try:
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("Không ghi được audit file cho event_id=%s: %s", event.event_id, e)
        return None

    return path


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def save_audit_and_memory(event: EventPayload, response: AgentResponse) -> Path | None:
    """
    Ghi audit record ra file JSON VÀ lưu vào pgvector LTM (agent_memory schema).

    Pipeline:
    1. Ghi JSON audit file (giữ nguyên hành vi cũ).
    2. Build context text → gọi get_embedding → upsert AgentExperienceLog vào PostgreSQL.
    
    Lỗi pgvector không block audit file. Mỗi bước fail độc lập và log warning.
    """
    # 1. Ghi file JSON audit (behavior cũ, không thay đổi)
    path = save_audit_record(event, response)

    # 2. Lưu vào pgvector LTM (không block nếu db không available)
    try:
        from app.database.session import async_session, init_db
        from app.database.models import AgentDecisionLog, AgentEnvironmentSnapshot, AgentExperienceLog
        from app.gateway.embeddings import get_embedding
        from sqlalchemy import select

        # Tự động khởi tạo schema & table nếu chưa tồn tại
        await init_db()

        # Build chuỗi context để embedding
        context_text = (
            f"Event: {event.event_type.value}. "
            f"Room: {event.room_id}. "
            f"Event data: {json.dumps(event.event_data, ensure_ascii=False)}. "
            f"Context: {json.dumps(event.operational_context, ensure_ascii=False)}"
        )

        vector = await get_embedding(context_text)

        recommended_tool = (
            response.recommendation.tool_name if response.recommendation else None
        )
        response_json = json.loads(response.model_dump_json())
        response_text = (
            f"Agent response for event {event.event_id}. "
            f"Event type: {event.event_type.value}. "
            f"Room: {event.room_id}. "
            f"Skip: {response.skip}. "
            f"Recommended tool: {recommended_tool}. "
            f"Analysis: {response.analysis}. "
            f"Full response: {json.dumps(response_json, ensure_ascii=False)}"
        )
        response_vector = await get_embedding(response_text)

        environment_context = event.operational_context.get("environment_context")
        environment_text = ""
        environment_vector: list[float] | None = None
        if environment_context:
            environment_text = (
                f"Environment readings from edge get_environment for event {event.event_id}. "
                f"Event type: {event.event_type.value}. "
                f"Room: {event.room_id}. "
                f"Payload: {json.dumps(environment_context, ensure_ascii=False)}"
            )
            environment_vector = await get_embedding(environment_text)

        async with async_session() as db:
            # Upsert: nếu event_id đã tồn tại thì update, tránh duplicate
            existing = await db.execute(
                select(AgentExperienceLog).where(AgentExperienceLog.id == str(event.event_id))
            )
            log_entry = existing.scalars().first()

            if log_entry is None:
                log_entry = AgentExperienceLog(
                    id=str(event.event_id),
                    event_type=event.event_type.value,
                    operational_context=event.operational_context,
                    context_embedding=vector,
                    agent_reasoning=response.analysis,
                    recommended_tool=recommended_tool,
                    is_fallback=response.is_fallback,
                    fallback_levels=response.fallback_levels,
                    # human_approved và env_reward được cập nhật sau bởi dashboard/worker
                )
                db.add(log_entry)
            else:
                log_entry.event_type = event.event_type.value
                log_entry.operational_context = event.operational_context
                log_entry.agent_reasoning = response.analysis
                log_entry.recommended_tool = recommended_tool
                log_entry.context_embedding = vector
                log_entry.is_fallback = response.is_fallback
                log_entry.fallback_levels = response.fallback_levels

            decision = await db.get(AgentDecisionLog, str(event.event_id))
            if decision is None:
                decision = AgentDecisionLog(
                    id=str(event.event_id),
                    event_id=str(event.event_id),
                    event_type=event.event_type.value,
                    room_id=str(event.room_id),
                    agent_response=response_json,
                    response_text=response_text,
                    response_embedding=response_vector,
                    analysis=response.analysis,
                    recommended_tool=recommended_tool,
                    skip=response.skip,
                    is_fallback=response.is_fallback,
                    fallback_levels=response.fallback_levels,
                )
                db.add(decision)
            else:
                decision.event_type = event.event_type.value
                decision.room_id = str(event.room_id)
                decision.agent_response = response_json
                decision.response_text = response_text
                decision.response_embedding = response_vector
                decision.analysis = response.analysis
                decision.recommended_tool = recommended_tool
                decision.skip = response.skip
                decision.is_fallback = response.is_fallback
                decision.fallback_levels = response.fallback_levels

            if environment_context and environment_vector is not None:
                snapshot_id = str(uuid5(NAMESPACE_URL, f"environment:{event.event_id}"))
                snapshot = await db.get(AgentEnvironmentSnapshot, snapshot_id)
                snapshot_payload = {
                    "id": snapshot_id,
                    "event_id": str(event.event_id),
                    "event_type": event.event_type.value,
                    "room_id": str(event.room_id),
                    "source": environment_context.get("source", "edge.query_tool.get_environment"),
                    "since": _parse_datetime(environment_context.get("since")),
                    "row_count": environment_context.get("row_count", 0),
                    "environment_context": environment_context,
                    "environment_text": environment_text,
                    "environment_embedding": environment_vector,
                }
                if snapshot is None:
                    snapshot = AgentEnvironmentSnapshot(**snapshot_payload)
                    db.add(snapshot)
                else:
                    for key, value in snapshot_payload.items():
                        if key != "id":
                            setattr(snapshot, key, value)

            await db.commit()
            logger.info(
                "Đã lưu agent memory vào pgvector: event_id=%s, tool=%s, environment_rows=%s",
                event.event_id,
                recommended_tool,
                environment_context.get("row_count", 0) if environment_context else 0,
            )
    except Exception as exc:
        logger.warning(
            "Không thể lưu vào pgvector LTM cho event_id=%s (không ảnh hưởng audit file): %s",
            event.event_id,
            exc,
        )

    return path
