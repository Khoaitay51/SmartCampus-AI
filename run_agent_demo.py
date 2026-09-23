"""
run_agent_demo.py
------------------
Script chạy AI Agent với dữ liệu THẬT lấy từ backend SmartCampus.

Khác với phiên bản mock cũ:
  - Kết quả được lưu vào pgvector LTM (save_audit_and_memory) phục vụ training RLHF.

Cách chạy:
  python run_agent_demo.py                     # chạy all 5 kịch bản mẫu
  python run_agent_demo.py --room <room_id>    # pull room thật từ backend và chạy
  python run_agent_demo.py --list-rooms        # liệt kê rooms có trên backend
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.agent.agent import ReActXenAgent
from app.config.settings import settings
from app.gateway.client import GatewayClient, GatewayError
from app.gateway.llm_client import LLMClient
from app.gateway.rag import execute_rag_tool
from app.gateway.rooms import RoomsClient
from app.logging.audit import save_audit_and_memory
from app.schemas.context import OperationalContext
from app.schemas.events import EventPayload, EventType

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_agent_demo")

# ---------------------------------------------------------------------------
# Training Scenarios — 5 kịch bản đa dạng cover các event_type chính
# ---------------------------------------------------------------------------

TRAINING_SCENARIOS: list[dict[str, Any]] = [
    # --- 1. Nhiệt độ tăng cao trong giờ học ---
    {
        "label": "Nhiệt độ tăng vọt giờ học (LECTURE mode)",
        "event": {
            "event_id": str(uuid4()),
            "event_type": EventType.TEMPERATURE_ANOMALY.value,
            "timestamp": "2026-09-22T08:30:00+07:00",
            "event_data": {
                "temperature": 36.2,
                "humidity": 71.0,
                "co2": 1450,
                "trigger": "threshold_exceeded",
                "threshold": 34.0,
            },
        },
        "context": {
            "room": {
                "room_name": "Phòng A101",
                "room_type": "lecture_hall",
                "current_mode": "LECTURE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-22T08:00:00+07:00",
                "window_end": "2026-09-22T08:30:00+07:00",
                "temperature": {"min": 28.5, "max": 36.2, "avg": 33.1, "latest": 36.2},
                "humidity": {"min": 60.0, "max": 75.0, "avg": 68.0, "latest": 71.0},
                "co2": {"min": 800.0, "max": 1450.0, "avg": 1100.0, "latest": 1450.0},
                "smoke_value": {"min": 0.0, "max": 2.0, "avg": 0.5, "latest": 0.0},
                "air_quality": {"min": 55.0, "max": 80.0, "avg": 65.0, "latest": 58.0},
            },
            "occupancy": {"current_count": 38, "total_in": 40, "total_out": 2, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "CS101",
                "lecturer_name": "TS. Nguyen Van A",
                "enrolled_count": 40,
                "checked_in_count": 38,
                "started_at": "2026-09-22T07:30:00+07:00",
                "attendance_deadline": "2026-09-22T07:45:00+07:00",
                "is_exam": False,
            },
            "recent_events": [
                {"type": "temperature_anomaly", "time": "2026-09-22T08:10:00+07:00", "extra": {"temperature": 34.5}},
            ],
        },
    },
    # --- 2. Phát hiện khói khẩn cấp trong lab ---
    {
        "label": "Khói khẩn cấp trong phòng lab (EMERGENCY mode)",
        "event": {
            "event_id": str(uuid4()),
            "event_type": EventType.SMOKE_DETECTED.value,
            "timestamp": "2026-09-22T09:45:00+07:00",
            "event_data": {
                "smoke_value": 620.0,
                "smoke_state": "suspected",
                "mq2_raw": 820,
                "trigger": "smoke_threshold_exceeded",
                "threshold": 400,
            },
        },
        "context": {
            "room": {
                "room_name": "Lab B202 — Hoa hoc",
                "room_type": "lab",
                "current_mode": "EMERGENCY",
                "smoke_state": "suspected",
            },
            "telemetry_summary": {
                "window_start": "2026-09-22T09:30:00+07:00",
                "window_end": "2026-09-22T09:45:00+07:00",
                "temperature": {"min": 27.0, "max": 40.5, "avg": 31.2, "latest": 40.5},
                "humidity": {"min": 45.0, "max": 65.0, "avg": 55.0, "latest": 58.0},
                "co2": {"min": 400.0, "max": 1800.0, "avg": 900.0, "latest": 1750.0},
                "smoke_value": {"min": 50.0, "max": 620.0, "avg": 310.0, "latest": 620.0},
                "air_quality": {"min": 20.0, "max": 60.0, "avg": 38.0, "latest": 22.0},
            },
            "occupancy": {"current_count": 6, "total_in": 8, "total_out": 2, "trend": "leaving"},
            "active_session": None,
            "recent_events": [],
        },
    },
    # --- 3. Thay đổi occupancy bất thường ngoài giờ học ---
    {
        "label": "Xam nhap bat thuong ngoai gio hoc (IDLE mode)",
        "event": {
            "event_id": str(uuid4()),
            "event_type": EventType.OCCUPANCY_CHANGE.value,
            "timestamp": "2026-09-22T22:15:00+07:00",
            "event_data": {
                "current_count": 4,
                "delta": 4,
                "direction": "in",
                "trigger": "occupancy_spike",
            },
        },
        "context": {
            "room": {
                "room_name": "Phong C305",
                "room_type": "study_room",
                "current_mode": "IDLE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-22T22:00:00+07:00",
                "window_end": "2026-09-22T22:15:00+07:00",
                "temperature": {"min": 25.0, "max": 26.0, "avg": 25.5, "latest": 25.8},
                "humidity": {"min": 55.0, "max": 62.0, "avg": 58.0, "latest": 60.0},
                "co2": {"min": 400.0, "max": 600.0, "avg": 480.0, "latest": 590.0},
                "smoke_value": {"min": 0.0, "max": 5.0, "avg": 1.5, "latest": 2.0},
                "air_quality": {"min": 80.0, "max": 95.0, "avg": 88.0, "latest": 85.0},
            },
            "occupancy": {"current_count": 4, "total_in": 4, "total_out": 0, "trend": "increasing"},
            "active_session": None,
            "recent_events": [],
        },
    },
    # --- 4. Thẻ RFID lạ trong giờ thi ---
    {
        "label": "The RFID khong xac dinh trong gio thi (EXAM mode)",
        "event": {
            "event_id": str(uuid4()),
            "event_type": EventType.RFID_UNKNOWN.value,
            "timestamp": "2026-09-22T13:05:00+07:00",
            "event_data": {
                "card_uid": "A3:F7:12:09",
                "reader_id": "door-main",
                "scan_result": "unknown",
            },
        },
        "context": {
            "room": {
                "room_name": "Phong thi A201",
                "room_type": "exam_room",
                "current_mode": "EXAM",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-22T12:50:00+07:00",
                "window_end": "2026-09-22T13:05:00+07:00",
                "temperature": {"min": 24.0, "max": 26.5, "avg": 25.2, "latest": 25.5},
                "humidity": {"min": 50.0, "max": 58.0, "avg": 54.0, "latest": 55.0},
                "co2": {"min": 400.0, "max": 700.0, "avg": 550.0, "latest": 680.0},
                "smoke_value": {"min": 0.0, "max": 1.0, "avg": 0.2, "latest": 0.0},
                "air_quality": {"min": 78.0, "max": 95.0, "avg": 87.0, "latest": 84.0},
            },
            "occupancy": {"current_count": 35, "total_in": 36, "total_out": 1, "trend": "stable"},
            "active_session": {
                "session_id": str(uuid4()),
                "class_code": "EXAM_FINAL_CS",
                "lecturer_name": "Hoi dong thi",
                "enrolled_count": 35,
                "checked_in_count": 35,
                "started_at": "2026-09-22T13:00:00+07:00",
                "attendance_deadline": "2026-09-22T13:15:00+07:00",
                "is_exam": True,
            },
            "recent_events": [],
        },
    },
    # --- 5. Nhân viên kỹ thuật bật thủ công (Manual trigger) ---
    {
        "label": "Ky thuat vien kich hoat thu cong dieu hoa (MAINTENANCE mode)",
        "event": {
            "event_id": str(uuid4()),
            "event_type": EventType.MANUAL_TRIGGER.value,
            "timestamp": "2026-09-22T07:00:00+07:00",
            "event_data": {
                "triggered_by": "staff_badge_0042",
                "intent": "pre_cool_before_class",
                "requested_tool": "set_fan",
                "notes": "Phong can lam mat truoc gio hoc 7:30",
            },
        },
        "context": {
            "room": {
                "room_name": "Phong A101",
                "room_type": "lecture_hall",
                "current_mode": "MAINTENANCE",
                "smoke_state": "normal",
            },
            "telemetry_summary": {
                "window_start": "2026-09-22T06:45:00+07:00",
                "window_end": "2026-09-22T07:00:00+07:00",
                "temperature": {"min": 30.0, "max": 33.0, "avg": 31.5, "latest": 33.0},
                "humidity": {"min": 70.0, "max": 80.0, "avg": 75.0, "latest": 78.0},
                "co2": {"min": 400.0, "max": 450.0, "avg": 420.0, "latest": 440.0},
                "smoke_value": {"min": 0.0, "max": 0.0, "avg": 0.0, "latest": 0.0},
                "air_quality": {"min": 80.0, "max": 95.0, "avg": 88.0, "latest": 90.0},
            },
            "occupancy": {"current_count": 1, "total_in": 1, "total_out": 0, "trend": "stable"},
            "active_session": None,
            "recent_events": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Helper: Lấy context thật từ backend
# ---------------------------------------------------------------------------

async def pull_context_from_backend(
    gw: GatewayClient, room_id: str, event_type: EventType
) -> tuple[EventPayload, OperationalContext] | None:
    """
    Pull dữ liệu thật từ backend cho room_id và xây dựng EventPayload + OperationalContext.
    Trả về None nếu backend không available.
    """
    rooms_client = RoomsClient(gw)
    try:
        room_detail = await rooms_client.get_room(room_id)
    except GatewayError as e:
        logger.error("Không lấy được room %s từ backend: %s", room_id, e)
        return None

    # Pull telemetry 15m gần nhất
    try:
        telemetry_raw = await rooms_client.get_telemetry(room_id, window="15m")
        telemetry_data = telemetry_raw if isinstance(telemetry_raw, list) else []
    except GatewayError:
        telemetry_data = []

    # Pull active session
    try:
        active_session = await rooms_client.get_active_session(room_id)
    except GatewayError:
        active_session = None

    # Pull history 1h gần nhất
    try:
        history = await rooms_client.get_history(room_id, hours=1)
    except GatewayError:
        history = []

    # Build telemetry_summary từ raw data
    def _summarize_metric(data: list[dict], key: str) -> dict:
        vals = [r.get(key) for r in data if r.get(key) is not None]
        if not vals:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "latest": 0.0}
        return {"min": min(vals), "max": max(vals), "avg": sum(vals) / len(vals), "latest": vals[-1]}

    room_state = room_detail.get("current_state", room_detail)
    context = OperationalContext.model_validate({
        "room": {
            "room_id": room_id,
            "room_name": room_detail.get("room_name", f"Room {room_id}"),
            "room_type": room_detail.get("room_type", "unknown"),
            "current_mode": room_state.get("mode", room_state.get("current_mode", "IDLE")),
            "smoke_state": room_state.get("smoke_state", "normal"),
        },
        "telemetry_summary": {
            "window_start": (datetime.now(timezone.utc)).isoformat(),
            "window_end": datetime.now(timezone.utc).isoformat(),
            "temperature": _summarize_metric(telemetry_data, "temperature"),
            "humidity": _summarize_metric(telemetry_data, "humidity"),
            "co2": _summarize_metric(telemetry_data, "co2"),
            "smoke_value": _summarize_metric(telemetry_data, "smoke_value"),
            "air_quality": _summarize_metric(telemetry_data, "air_quality"),
        },
        "occupancy": room_state.get("occupancy", {"current_count": 0, "total_in": 0, "total_out": 0, "trend": "unknown"}),
        "active_session": active_session,
        "recent_events": history[:5] if history else [],
    })

    latest_temp = context.telemetry_summary.temperature.get("latest") if context.telemetry_summary else None
    event = EventPayload.model_validate({
        "event_id": str(uuid4()),
        "event_type": event_type.value,
        "room_id": room_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_data": {
            "temperature": latest_temp,
            "source": "live_pull",
            "room_mode": context.room.current_mode,
        },
        "operational_context": context.model_dump(mode="json"),
    })
    return event, context


# ---------------------------------------------------------------------------
# Helper: Build event + context từ training scenario (offline/fallback)
# ---------------------------------------------------------------------------

def build_scenario(scenario: dict[str, Any], room_id: str | None = None) -> tuple[EventPayload, OperationalContext]:
    """Xây dựng EventPayload + OperationalContext từ training scenario dict."""
    rid = room_id or str(uuid4())
    event_data = dict(scenario["event"])
    event_data["room_id"] = rid
    event_data.setdefault("operational_context", scenario.get("context", {}))
    event = EventPayload.model_validate(event_data)

    ctx_data = dict(scenario["context"])
    ctx_data["room"] = {**ctx_data["room"], "room_id": rid}
    context = OperationalContext.model_validate(ctx_data)
    return event, context


# ---------------------------------------------------------------------------
# Core: Chạy một kịch bản và lưu kết quả
# ---------------------------------------------------------------------------

async def run_scenario(
    label: str,
    event: EventPayload,
    context: OperationalContext,
    llm: LLMClient,
    save_memory: bool = True,
) -> None:
    """Chạy agent với event + context, in kết quả, lưu audit + LTM."""
    print(f"\n{'─' * 70}")
    print(f" {label}")
    print(f"     Event ID   : {event.event_id}")
    print(f"     Event Type : {event.event_type.value}")
    print(f"     Room Mode  : {context.room.current_mode}")
    print(f"{'─' * 70}")

    agent = ReActXenAgent(llm=llm, execute_rag_tool=execute_rag_tool)

    try:
        response = await agent.evaluate(event, context)
    except Exception as exc:
        logger.error("Agent evaluate thất bại cho event %s: %s", event.event_id, exc)
        return

    print(f"\n Kết quả Agent:")
    print(f"     skip       : {response.skip}")
    if response.skip_reason:
        print(f"     skip_reason: {response.skip_reason}")
    print(f"     analysis   : {response.analysis[:200]}{'...' if len(response.analysis) > 200 else ''}")

    if response.recommendation:
        r = response.recommendation
        print(f"\n Recommendation:")
        print(f"     tool       : {r.tool_name}")
        print(f"     params     : {json.dumps(r.tool_params, ensure_ascii=False)}")
        print(f"     confidence : {r.confidence:.2f}")
        print(f"     urgency    : {r.urgency}")
        print(f"     reason     : {r.reason[:150]}{'...' if len(r.reason) > 150 else ''}")

    if response.alternatives:
        print(f"\n Alternatives ({len(response.alternatives)}):")
        for alt in response.alternatives:
            print(f"     - {alt.tool_name} (conf={alt.confidence:.2f}): {alt.reason[:80]}")

    if response.tool_calls_log:
        print(f"\n RAG Tool Calls ({len(response.tool_calls_log)}):")
        for tc in response.tool_calls_log:
            print(f"     [{tc.tool}] → {tc.result_summary[:100]}")

    print(f"\n Reasoning Trace ({len(response.structured_trace)} steps):")
    for step in response.structured_trace:
        tool_str = f"  tool={step.tool}" if step.tool else ""
        print(f"     [Step {step.step}] {step.decision} | {step.reason_code}{tool_str}")

    # Lưu audit file + pgvector LTM
    if save_memory:
        try:
            path = await save_audit_and_memory(event, response)
            if path:
                print(f"\n Audit saved → {path}")
        except Exception as exc:
            logger.warning("Không lưu được audit/memory: %s", exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    parser = argparse.ArgumentParser(description="SmartCampus AI Agent — Training Demo Runner")
    parser.add_argument("--room", help="Room ID thật để pull từ backend và chạy agent")
    parser.add_argument("--event-type", default="temperature_anomaly", help="Loại event khi dùng --room")
    parser.add_argument("--list-rooms", action="store_true", help="Liệt kê rooms có sẵn trên backend")
    parser.add_argument("--no-memory", action="store_true", help="Không lưu vào pgvector LTM")
    parser.add_argument("--scenario", type=int, help="Chỉ chạy kịch bản số N (0-indexed)")
    args = parser.parse_args()

    print("=" * 70)
    print(" SmartCampus AI Agent — Training Demo")
    print(f"       Backend : {settings.BACKEND_BASE_URL}")
    print(f"       LLM     : {settings.AGENT}")
    print("=" * 70)

    llm = LLMClient()
    save_memory = not args.no_memory

    async with GatewayClient(base_url=settings.BACKEND_BASE_URL) as gw:
        # Mode: liệt kê rooms
        if args.list_rooms:
            rooms_client = RoomsClient(gw)
            try:
                rooms = await rooms_client.list_rooms()
                print(f"\n Danh sách rooms trên backend ({len(rooms)} phòng):")
                for r in rooms:
                    print(f"    - {r.get('room_id')} | {r.get('room_name')} | mode={r.get('current_mode','?')}")
            except GatewayError as e:
                print(f" Không kết nối được backend: {e}")
            return

        # Mode: pull room thật từ backend
        if args.room:
            print(f"\n Pull dữ liệu thật từ backend cho room: {args.room}")
            try:
                event_type = EventType(args.event_type)
            except ValueError:
                print(f"  event_type không hợp lệ: {args.event_type}")
                return

            result = await pull_context_from_backend(gw, args.room, event_type)
            if result is None:
                print(" Không lấy được dữ liệu từ backend.")
                return
            event, context = result
            await run_scenario(
                label=f"Live Backend — {args.room} ({event_type.value})",
                event=event,
                context=context,
                llm=llm,
                save_memory=save_memory,
            )
            return

        # Mode mặc định: chạy training scenarios offline
        scenarios = TRAINING_SCENARIOS
        if args.scenario is not None:
            if args.scenario < 0 or args.scenario >= len(scenarios):
                print(f" Kịch bản {args.scenario} không tồn tại. Có {len(scenarios)} kịch bản (0-{len(scenarios)-1}).")
                return
            scenarios = [scenarios[args.scenario]]

        print(f"\n Chạy {len(scenarios)} kịch bản training (LLM thật, RAG gọi backend nếu available)...")

        for i, scenario in enumerate(scenarios):
            try:
                if i > 0:
                    logger.info("Nghỉ 5s giữa các kịch bản để tránh nổ Rate Limit Gemini Free Tier (5 requests/phút)...")
                    await asyncio.sleep(5)

                room_id = str(uuid4())
                event, context = build_scenario(scenario, room_id)

                # Thử pull telemetry thật từ backend nếu có
                # (nếu backend down, dùng dữ liệu context từ scenario)
                await run_scenario(
                    label=f"[{i + 1}/{len(TRAINING_SCENARIOS)}] {scenario['label']}",
                    event=event,
                    context=context,
                    llm=llm,
                    save_memory=save_memory,
                )
            except Exception as exc:
                logger.error("Lỗi kịch bản %d: %s", i, exc)
                continue

    print("\n" + "=" * 70)
    print(" Hoàn thành tất cả kịch bản. Kết quả lưu tại:")
    print(f"       JSON audit : {settings.AUDIT_OUTPUT_DIR}/")
    print(f"       pgvector   : agent_memory.agent_experience_logs (schema)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
