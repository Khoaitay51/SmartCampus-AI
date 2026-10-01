"""
seed_all_data.py
-----------------
Seeds Edge DB (port 5433) and AI DB (port 5432) with data matching
the telemetry window already inserted:

  Telemetry window: 2026-10-01 09:24 -> 10:24 (Vietnam, +07:00)
                  = 2026-10-01 02:24 -> 03:24 UTC

Seeded data:
  [Edge DB - port 5433]
  - users: 1 lecturer
  - classes: CS101 (A101), NET202 (A102)
  - room_sessions: active sessions 08:00-12:00 for both rooms
  - room_state: state transitions covering the window
  - Endpoints to add: /api/rooms/{id}/history, /api/rag/schedule

  [AI DB - port 5432]
  - agent_memory.campus_documents: SOPs for CO2, temp, smoke
  - agent_memory.contextual_memory_logs: room A101 daily summary
"""

import asyncio
import asyncpg
import uuid
from datetime import datetime, timezone, timedelta


# ── Connection strings ──────────────────────────────────────────────────────
EDGE_DSN = "postgresql://smartcampus:change-this-local-password@localhost:5433/smartcampus"
AI_DSN   = "postgresql://smartcampus:change-this-local-password@localhost:5432/smartcampus"

# ── Fixed IDs ───────────────────────────────────────────────────────────────
ROOM_A101 = "0c5bc15f-d2ef-4450-b7f3-b0d0a2dc726d"
ROOM_A102 = "b669e4b5-a922-45fa-997c-546d539c1b4a"

LECTURER_ID  = "aaaaaaaa-0000-0000-0000-000000000001"
CLASS_ID_101 = "bbbbbbbb-0000-0000-0000-000000000001"
CLASS_ID_202 = "bbbbbbbb-0000-0000-0000-000000000002"
SESSION_ID_101 = "cccccccc-0000-0000-0000-000000000001"
SESSION_ID_202 = "cccccccc-0000-0000-0000-000000000002"

# ── Time window (Vietnam +07:00) ─────────────────────────────────────────────
# Telemetry already in DB: 09:24 -> 10:24 local = 02:24 -> 03:24 UTC
# Session covers:          08:00 -> 12:00 local = 01:00 -> 05:00 UTC
TZ_VN = timezone(timedelta(hours=7))
TODAY  = datetime(2026, 10, 1, tzinfo=TZ_VN)

SESSION_START = TODAY.replace(hour=8,  minute=0,  second=0, microsecond=0)
SESSION_END   = TODAY.replace(hour=12, minute=0,  second=0, microsecond=0)
DEADLINE      = TODAY.replace(hour=8,  minute=30, second=0, microsecond=0)


# ── Helpers ──────────────────────────────────────────────────────────────────
def ts(dt): return dt  # asyncpg accepts aware datetime directly


# ============================================================================
# PART 1 — EDGE DB (port 5433)
# ============================================================================
async def seed_edge(conn):
    print("\n[EDGE DB] Seeding users, classes, sessions, room_state...")

    # 1a. Lecturer user
    await conn.execute("""
        INSERT INTO users (user_id, role, username, full_name, is_active)
        VALUES ($1, 'LECTURER', 'lecturer01', 'Nguyen Van Giao', 1)
        ON CONFLICT (user_id) DO NOTHING;
    """, uuid.UUID(LECTURER_ID))
    print("  + user: Nguyen Van Giao (LECTURER)")

    # 1b. Classes
    await conn.execute("""
        INSERT INTO classes (class_id, class_code, class_name, lecturer_id, is_active)
        VALUES ($1, 'CS101', 'Nhap mon IoT', $2, true)
        ON CONFLICT (class_id) DO NOTHING;
    """, uuid.UUID(CLASS_ID_101), uuid.UUID(LECTURER_ID))

    await conn.execute("""
        INSERT INTO classes (class_id, class_code, class_name, lecturer_id, is_active)
        VALUES ($1, 'NET202', 'Mang may tinh', $2, true)
        ON CONFLICT (class_id) DO NOTHING;
    """, uuid.UUID(CLASS_ID_202), uuid.UUID(LECTURER_ID))
    print("  + classes: CS101 (A101), NET202 (A102)")

    # 1c. Room sessions (08:00-12:00, still ACTIVE at 10:24)
    await conn.execute("""
        INSERT INTO room_sessions
            (session_id, room_id, lecturer_id, class_id, class_code,
             session_start_timestamp, attendance_deadline_timestamp,
             session_end_timestamp, is_exam, session_status)
        VALUES ($1,$2,$3,$4,'CS101',$5,$6,$7,false,'active')
        ON CONFLICT (session_id) DO NOTHING;
    """, uuid.UUID(SESSION_ID_101), uuid.UUID(ROOM_A101), uuid.UUID(LECTURER_ID),
         uuid.UUID(CLASS_ID_101), ts(SESSION_START), ts(DEADLINE), ts(SESSION_END))

    await conn.execute("""
        INSERT INTO room_sessions
            (session_id, room_id, lecturer_id, class_id, class_code,
             session_start_timestamp, attendance_deadline_timestamp,
             session_end_timestamp, is_exam, session_status)
        VALUES ($1,$2,$3,$4,'NET202',$5,$6,$7,false,'active')
        ON CONFLICT (session_id) DO NOTHING;
    """, uuid.UUID(SESSION_ID_202), uuid.UUID(ROOM_A102), uuid.UUID(LECTURER_ID),
         uuid.UUID(CLASS_ID_202), ts(SESSION_START), ts(DEADLINE), ts(SESSION_END))
    print(f"  + sessions: CS101@A101, NET202@A102  [{SESSION_START.strftime('%H:%M')}-{SESSION_END.strftime('%H:%M')} VN]")

    # 1d. Room state transitions for A101 (SAVING -> LECTURE when class started)
    states_a101 = [
        (TODAY.replace(hour=7, minute=0),  "SAVING",  "offline"),
        (TODAY.replace(hour=8, minute=0),  "LECTURE", "online"),
    ]
    states_a102 = [
        (TODAY.replace(hour=7, minute=0),  "SAVING",  "offline"),
        (TODAY.replace(hour=8, minute=0),  "LECTURE", "online"),
    ]
    for (t, mode, status) in states_a101:
        await conn.execute("""
            INSERT INTO room_state (room_state_timestamp, room_id, room_mode, room_status)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING;
        """, ts(t), uuid.UUID(ROOM_A101), mode, status)

    for (t, mode, status) in states_a102:
        await conn.execute("""
            INSERT INTO room_state (room_state_timestamp, room_id, room_mode, room_status)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING;
        """, ts(t), uuid.UUID(ROOM_A102), mode, status)
    print("  + room_state: SAVING@07:00 -> LECTURE@08:00 (both rooms)")

    print("[EDGE DB] Done.")


# ============================================================================
# PART 2 — AI DB (port 5432) — campus_documents (no embedding needed)
# ============================================================================
async def seed_ai(conn):
    print("\n[AI DB] Seeding campus_documents and contextual_memory_logs...")

    docs = [
        ("doc-co2-sop",   "sop", "Quy trinh xu ly CO2 vuot nguong",
         "Nguong CO2 an toan: duoi 1000 ppm. 1000-1500ppm: CANH BAO - bat quat. 1500-2500ppm: NGUY HIEM - mo cua. >2500ppm: KHAN CAP - soi tan lop. Hanh dong: Goi tool set_fan(state=on). Neu sau 10 phut CO2 khong giam, leo thang len khan cap."),

        ("doc-temp-sop",  "sop", "Quy trinh xu ly nhiet do bat thuong",
         "Nguong nhiet do an toan: 15-30 do C. 30-35 do C: CANH BAO - bat quat/dieu hoa. >35 do C: NGUY HIEM - bat quat toi da. >40 do C: KHAN CAP - kiem tra hoa hoan. Hanh dong: Goi set_fan(state=on). Neu co hoa hoan, uu tien bao chay."),

        ("doc-smoke-sop", "sop", "Quy trinh phat hien khoi",
         "Cam bien khoi MQ2. Nguong smoke_value > 400. 400-600: NGHI NGO - kiem tra nguon khoi. >600: CANH BAO CHAY - kich hoat bao dong, soi tan, goi 114."),

        ("doc-policy-01", "policy", "Chinh sach phong hoc thong minh",
         "Mode LECTURE: dang co lop hoc. Mode SAVING: ngoai gio hoc. Mode LOCK: phong bi khoa. Moi su co moi truong trong gio hoc phai xu ly trong 5 phut."),
    ]

    for (doc_id, doc_type, title, content) in docs:
        await conn.execute("""
            INSERT INTO agent_memory.campus_documents (id, doc_type, title, content)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO NOTHING;
        """, doc_id, doc_type, title, content)
    print(f"  + campus_documents: {len(docs)} SOPs/policies")

    summary_a101 = ("Lich su phong A101 ngay 2026-10-01: 07:00 SAVING, 08:00 bat dau CS101 - Nhap mon IoT (giang vien Nguyen Van Giao). "
                    "09:24-10:19: cam bien on dinh (nhiet do ~25C, CO2 400-600ppm). "
                    "10:19-10:24: CO2 tang dot ngot len 1500-5000ppm, nhiet do 30-45 do C. "
                    "Phan loai: Su co moi truong nghiem trong trong gio hoc.")

    summary_a102 = ("Lich su phong A102 ngay 2026-10-01: 07:00 SAVING, 08:00 bat dau NET202 - Mang may tinh. "
                    "09:24-10:24: cam bien on dinh (nhiet do 24-26C, CO2 400-600ppm).")

    period_start = TODAY.replace(hour=7, minute=0)
    period_end   = TODAY.replace(hour=10, minute=24)

    logs = [
        ("ctx-a101-daily", ROOM_A101, summary_a101),
        ("ctx-a102-daily", ROOM_A102, summary_a102),
    ]
    for (log_id, room_id, summary) in logs:
        await conn.execute("""
            INSERT INTO agent_memory.contextual_memory_logs
                (id, room_id, period, start_time, end_time, summary_text)
            VALUES ($1, $2, 'daily', $3, $4, $5)
            ON CONFLICT (id) DO NOTHING;
        """, log_id, room_id, ts(period_start), ts(period_end), summary)
    print("  + contextual_memory_logs: daily summary for A101, A102")

    print("[AI DB] Done.")


# ============================================================================
# MAIN
# ============================================================================
async def main():
    print("=" * 60)
    print("SmartCampus Seed Script")
    print(f"Session window (VN time): {SESSION_START.strftime('%Y-%m-%d %H:%M')} - {SESSION_END.strftime('%H:%M')}")
    print(f"Telemetry window (VN):    2026-10-01 09:24 - 10:24")
    print("=" * 60)

    edge = await asyncpg.connect(EDGE_DSN)
    ai   = await asyncpg.connect(AI_DSN)

    try:
        await seed_edge(edge)
        await seed_ai(ai)
    finally:
        await edge.close()
        await ai.close()

    print("\n" + "=" * 60)
    print("SEED COMPLETE. Summary:")
    print("  Edge DB (5433): users, classes, room_sessions, room_state")
    print("  AI DB   (5432): campus_documents (SOPs), contextual_memory_logs")
    print("=" * 60)
    print("\nTo query schedule: GET /api/rag/schedule?room_id=<id>")
    print("To query history:  GET /api/rooms/<id>/history?hours=24")
    print("NOTE: These 2 endpoints not yet in Edge API - see next step.")

if __name__ == "__main__":
    asyncio.run(main())
