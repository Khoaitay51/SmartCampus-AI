from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

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
        from app.database.models import AgentExperienceLog
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
                    # human_approved và env_reward được cập nhật sau bởi dashboard/worker
                )
                db.add(log_entry)
            else:
                log_entry.agent_reasoning = response.analysis
                log_entry.recommended_tool = recommended_tool
                log_entry.context_embedding = vector

            await db.commit()
            logger.info(
                "Đã lưu AgentExperienceLog vào pgvector LTM: event_id=%s, tool=%s",
                event.event_id,
                recommended_tool,
            )
    except Exception as exc:
        logger.warning(
            "Không thể lưu vào pgvector LTM cho event_id=%s (không ảnh hưởng audit file): %s",
            event.event_id,
            exc,
        )

    return path