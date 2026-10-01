"""
app/api/audit.py
----------------
REST API endpoints cho Audit Logs & Tool Activity.
Truy vấn trực tiếp từ các file audit JSON đã ghi trong settings.AUDIT_OUTPUT_DIR
và từ bảng agent_decision_logs / agent_experience_logs trong PostgreSQL.
Hỗ trợ xuất file CSV.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_active_user
from app.auth.models import User
from app.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


def _load_audit_files(limit: int = 100) -> list[dict[str, Any]]:
    """Đọc các file audit JSON gần nhất từ thư mục output."""
    out_dir = Path(settings.AUDIT_OUTPUT_DIR)
    if not out_dir.exists():
        return []

    files = sorted(out_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    records = []
    for f in files[:limit]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            records.append(data)
        except Exception as e:
            logger.warning("Không đọc được file audit %s: %s", f.name, e)
    return records


@router.get("")
async def get_audit_logs(
    log_type: Optional[str] = Query(None, description="'tool_calls' hoặc 'fallback' hoặc None (tất cả)"),
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    """Trả về danh sách các bản ghi audit (Agent Tool Calls & Fallback Audit)."""
    raw_records = _load_audit_files(limit=limit)
    result = []

    for r in raw_records:
        rec_time = r.get("recorded_at") or r.get("event", {}).get("timestamp") or ""
        ts_str = rec_time[11:19] if len(rec_time) >= 19 else "Vừa xong"
        full_date = rec_time[:10] if len(rec_time) >= 10 else ""

        response = r.get("response", {})
        tool_calls = response.get("tool_calls_log") or []
        fallback_logs = response.get("fallback_audit_log") or []
        is_fallback = response.get("is_fallback", False)
        event_id = r.get("event", {}).get("event_id") or response.get("event_id") or "EVT-UNKNOWN"
        room_id = r.get("event", {}).get("room_id") or "Campus"

        # 1. Thu thập Tool Calls
        if log_type != "fallback":
            if tool_calls:
                for tc in tool_calls:
                    tool_name = tc.get("tool") or tc.get("tool_name") or "unknown_tool"
                    summary = tc.get("result_summary") or str(tc.get("params") or "")
                    result.append({
                        "id": f"{event_id}_tc_{tool_name}",
                        "timestamp": ts_str,
                        "date": full_date,
                        "type": "Agent Tool Calls",
                        "component": tc.get("component") or "react_agent",
                        "target": tool_name,
                        "detail": summary[:120] if len(summary) > 120 else summary,
                        "level": tc.get("level") or "INFO",
                        "room_id": room_id,
                        "event_id": event_id,
                    })
            else:
                # Nếu không có tool calls riêng nhưng có recommendation
                rec = response.get("recommendation")
                if rec:
                    result.append({
                        "id": f"{event_id}_rec",
                        "timestamp": ts_str,
                        "date": full_date,
                        "type": "Agent Tool Calls",
                        "component": "react_agent",
                        "target": rec.get("tool_name", "evaluate"),
                        "detail": rec.get("reason", "Đề xuất điều khiển thiết bị")[:120],
                        "level": "INFO",
                        "room_id": room_id,
                        "event_id": event_id,
                    })

        # 2. Thu thập Fallback Logs
        if log_type != "tool_calls":
            if fallback_logs:
                for fb in fallback_logs:
                    result.append({
                        "id": f"{event_id}_fb_{fb.get('level', 'L')}",
                        "timestamp": ts_str,
                        "date": full_date,
                        "type": "Fallback Audit",
                        "component": fb.get("component") or "ai_service",
                        "target": str(fb.get("level") or "LEVEL_1"),
                        "detail": fb.get("detail") or "Fallback activation",
                        "level": "WARN",
                        "room_id": room_id,
                        "event_id": event_id,
                    })
            elif is_fallback:
                result.append({
                    "id": f"{event_id}_fb_auto",
                    "timestamp": ts_str,
                    "date": full_date,
                    "type": "Fallback Audit",
                    "component": "fallback_orchestrator",
                    "target": "LEVEL_1",
                    "detail": response.get("analysis") or "Đã chuyển đổi sang mô hình dự phòng",
                    "level": "WARN",
                    "room_id": room_id,
                    "event_id": event_id,
                })

    return result[:limit]


@router.get("/export")
async def export_audit_csv(
    log_type: Optional[str] = Query(None),
    _user: User = Depends(get_current_active_user),
):
    """Xuất toàn bộ Audit logs dưới dạng file CSV chuẩn RFC 4180."""
    raw_logs = await get_audit_logs(log_type=log_type, limit=200, _user=_user)

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["ID", "Timestamp", "Date", "Type", "Component", "Target / Tool", "Detail", "Level", "Room ID", "Event ID"])

    for item in raw_logs:
        writer.writerow([
            item.get("id"),
            item.get("timestamp"),
            item.get("date"),
            item.get("type"),
            item.get("component"),
            item.get("target"),
            item.get("detail"),
            item.get("level"),
            item.get("room_id"),
            item.get("event_id"),
        ])

    output.seek(0)
    filename = f"smartcampus_audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
