from __future__ import annotations
 
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
 
from app.config.settings import settings
from app.schemas.events import EventPayload
from app.schemas.recommendation import AgentResponse

# mỗi khi /evaluate xử lý xong, ghi 1 file JSON audit gồm: input event + output response (+ replay thoi gian cu the)
# đc ghi trước khi trả response về gateway
logger = logging.getLogger(__name__)

def _output_path(event_id: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(settings.AUDIT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{ts}_{event_id}.json"

def save_audit_record(event: EventPayload, response: AgentResponse) -> Path | None:
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