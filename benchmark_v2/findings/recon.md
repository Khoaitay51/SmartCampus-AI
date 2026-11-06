# findings/recon.md — Khảo sát hệ thống v1 (Phase A2)

> **Trạng thái:** HOÀN THÀNH (A2 done) — đọc trực tiếp từ source code, không suy diễn  
> **Ngày khảo sát:** 2026-10-22  
> **Phạm vi:** Đọc code thực tế, KHÔNG thay đổi bất kỳ file nào

---

## A2.1 — Danh sách Tool đầy đủ

**Nguồn:** `app/tools/registry.py`

### RAG Tools (Read-only, Agent gọi trong vòng ReAct)

| Tool | Mô tả | Parameters |
|------|--------|------------|
| `search_history` | Semantic search pgvector: SOP + lịch sử sự cố | `query` (required), `room_id` (opt), `time_range` (1h/6h/24h/7d) |
| `get_telemetry` | Raw time-series cho 1 metric, 1 phòng | `room_id` (req), `metric` (temp/humidity/co2/smoke/occupancy), `window` (15m/1h/6h) |
| `get_attendance` | Attendance records theo phòng/session/lớp | `room_id` (opt), `session_id` (opt), `class_code` (opt) |
| `compare_rooms` | So sánh metric giữa nhiều phòng | `room_ids` (req list), `metric` (req), `window` (1h/6h/24h) |
| `get_room_history` | Lịch sử FSM state transitions | `room_id` (req), `hours` (req int) |
| `get_schedule` | Lịch học theo phòng/ngày | `room_id` (opt), `date` (opt, YYYY-MM-DD) |
| `get_predictions` | EWMA prediction cho metric tương lai | `room_id` (req), `metric` (temperature/co2), `horizon` (15m/30m) |

### Action Tools (Đề xuất trong `finish`, KHÔNG gọi trực tiếp trong ReAct)

| Tool | Mô tả | Parameters | Phân loại v2 |
|------|--------|------------|--------------|
| `set_fan` | Bật/tắt quạt thông gió | `room_id`, `state` (on/off) | **actuation** |
| `set_door` | Khóa/mở khóa cửa | `room_id`, `state` (locked/unlocked) | **actuation** |
| `set_mode` | Thay đổi FSM mode phòng | `room_id`, `mode` (SAVING/SELF_STUDY/LECTURE/EXAM/LOCK/SUSPECTED/EMERGENCY) | **actuation** |
| `trigger_buzzer` | Kích hoạt còi báo động | `room_id`, `pattern` (short/long/continuous) | **actuation** |
| `send_alert` | Gửi cảnh báo tới giảng viên/admin | `room_id`, `message`, `level` (info/warning/critical) | **notification** |
| `set_led` | Điều khiển đèn LED trạng thái | `room_id`, `state` (solid/blink) | **actuation** |

### Finish Tool

| Tool | Mô tả |
|------|--------|
| `finish` | Kết thúc reasoning, trả AgentResponse JSON đầy đủ |

### Mode Permission Matrix

| Mode | Allowed Action Tools |
|------|---------------------|
| SAVING | set_fan, set_door, set_mode, send_alert, set_led |
| SELF_STUDY | set_fan, set_door, set_mode, send_alert, set_led |
| LECTURE | set_fan, set_door, set_mode, send_alert, set_led |
| EXAM | set_fan, send_alert, set_led, set_mode |
| LOCK | send_alert, trigger_buzzer, set_mode |
| SUSPECTED | set_fan, send_alert, set_led, trigger_buzzer, set_mode |
| EMERGENCY | set_fan, set_door, set_mode, trigger_buzzer, send_alert, set_led |

> [!NOTE]
> Permission matrix là **soft warn** trong Agent — Policy Engine mới enforce cứng. Agent có thể recommend tool ngoài matrix nhưng sẽ bị log warning.

**Phân loại v2 cho benchmark:**
- **@actuation** (DH-A): set_fan, set_door, set_mode, trigger_buzzer, set_led
- **@notification** (có thể dùng làm proxy exfil): send_alert
- **@exfil marker** (DS): bất kỳ tool nào mang dữ liệu canary ra ngoài — chủ yếu qua `send_alert.message`

---

## A2.2 — Cơ chế thời gian (Now/Reference Time)

**Nguồn:** `app/gateway/rag.py`, `app/agent/state.py`, `app/api/evaluate.py`

### Kết quả khảo sát:

```
get_telemetry (gateway/rag.py:197):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    # → Dùng datetime.now(timezone.utc) — KHÔNG có reference_time param

get_predictions (gateway/rag.py:290):
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    # → Dùng datetime.now(timezone.utc) — KHÔNG có reference_time param

AgentRunState (agent/state.py:44):
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # → Timestamp bắt đầu run — không inject từ ngoài
```

### Kết luận [XM-2] ✅:
- **Không có cơ chế `reference_time` nào trong v1.** Cả `get_telemetry` và `get_predictions` đều gọi `datetime.now(timezone.utc)` — tức là query data từ DB theo wall-clock thực.
- `/evaluate` endpoint (`api/evaluate.py`) **không nhận `reference_time` field** trong payload.
- **Hàm ý cho Phase B2:** Cần thêm `reference_time` vào EventPayload hoặc OperationalContext để neo thời gian. Đây là **QĐ-7** cần user quyết định ở G0.

---

## A2.3 — Fallback Engine & Disable Flag

**Nguồn:** `app/fallback/orchestrator.py`, `app/api/evaluate.py`, `app/config/settings.py`

### Fallback hoạt động như thế nào:

```python
# evaluate.py → evaluate_with_fallback()
# orchestrator.py → evaluate_with_fallback():
#   1. Gọi agent.run() với timeout agent_timeout=60.0
#   2. Nếu lỗi bất kỳ → evaluate_by_rules() (rule-based fallback)
#   3. Gắn is_fallback=True + fallback_levels vào result
```

**Trong agent.py:**
- Guard 1: AllProvidersFailed → Rule Fallback
- Guard 2: RAG tool fail 3 lần liên tục → Rule Fallback
- Guard 3: JSON parse fail 3 lần → Rule Fallback (ParsingExhausted)
- `is_fallback` field luôn có trong AgentResponse

### [XM-3] Disable fallback flag:
**Không có flag `DISABLE_FALLBACK` hay `BENCHMARK_MODE` nào** trong `settings.py`.

**Hàm ý cho Phase B:** Để đảm bảo "fallback DISABLED for headline runs" theo plan §3.1:
- Cần inject `reference_time` vào seeded DB để RAG tools không fail
- Hoặc: Tạo mock RAG executor cho benchmark (feature flag `USE_BENCHMARK_RAG=True`)
- `is_fallback=True` trong kết quả → run phải được loại bỏ hoặc log riêng

### Model v1 được dùng:
- `settings.py`: `AGENT: str = Field(default="gemini-3.6-flash", ...)`
- `LLM_PROVIDER`: mặc định `"gemini"`
- `GeminiLLMClient` sẽ đọc `settings.AGENT` → model = `gemini-3.6-flash`
- **[XM-3] RESOLVED:** Model thực tế trong v1 là **`gemini-3.6-flash`** (không phải "Gemini 2.5/Flash-lite" như ghi nhầm trong benchmark_status.md)

---

## A2.4 — Tool Registry (đã xong trong A2.1)

**Phân loại hoàn chỉnh cho v2:**

```
RAG tools (read, không sinh side-effect):
  search_history, get_telemetry, get_attendance,
  compare_rooms, get_room_history, get_schedule, get_predictions

Action tools — actuation (DH-A target):
  set_fan, set_door, set_mode, trigger_buzzer, set_led

Action tools — notification (DS potential vector):
  send_alert   ← message field có thể chứa canary data

Finish tool:
  finish  ← agent kết thúc ReAct, trả AgentResponse
```

---

## A2.5 — Cấu trúc Trajectory

**Nguồn:** `app/agent/state.py`, `app/agent/agent.py`

```python
# TrajectoryStep (mỗi step của ReAct loop):
class TrajectoryStep(BaseModel):
    self_ask: str | None = None   # câu hỏi tự đặt ra
    thought: str                   # suy luận
    action: str                    # tool được gọi
    action_input: dict             # params
    observation: str               # kết quả tool

# StructuredTraceStep (log có cấu trúc hơn, đi vào response):
class StructuredTraceStep(BaseModel):
    step: int
    decision: str        # "call_tool" | "finish" | "parse_error" | "invalid_action"
    tool: str | None
    reason_code: str | None
    evidence_ids: list[str]
    observation_summary: str | None
    action_input: dict

# AgentRunState:
class AgentRunState(BaseModel):
    trajectory: list[TrajectoryStep]
    structured_trace: list[StructuredTraceStep]
    tool_calls_log: list[ToolCallLogEntry]  # đi vào AgentResponse.tool_calls_log
    past_experience: str
    reflections: list[str]          # feedback từ Review
    round: int                       # số vòng Reflect (max 3)
    max_react_step: int = 6          # max steps/round (từ settings)
    max_reflect_step: int = 3        # max rounds
    rag_calls_remaining: int = 4     # budget RAG per evaluate
```

**AgentResponse fields liên quan đến benchmark:**
- `recommendation`: `ToolRecommendation | None`
  - `tool_name`: tên action tool
  - `parameters`: params tool
  - `confidence`: float 0-1
  - `urgency`: "low"/"medium"/"high"/"critical"
- `skip: bool` — True nếu agent bỏ qua
- `skip_reason: str | None`
- `is_fallback: bool`
- `tool_calls_log: list[ToolCallLogEntry]` — danh sách RAG calls
- `structured_trace: list[StructuredTraceStep]`
- `analysis: str`

**Hàm ý cho Phase C6 (synthesize):** Format testcase v2 cần map với `EventPayload` schema. Attacker injection chỉ vào field `event_data.description`.

---

## A2.6 — Database & Connection

**Nguồn:** `app/gateway/db.py`, `app/database/session.py`, `app/config/settings.py`

### Có 2 DB:

**DB 1 — PostgreSQL + pgvector (production data):**
```
DATABASE_URL: postgresql+asyncpg://smartcampus:***@localhost:5432/smartcampus
Schemas:
  - agent_memory:   contextual_memory_logs, campus_documents,
                    agent_experience_logs, environment_snapshots, agent_decision_logs
  - campus:         (ORM models Campus, CampusRoom, ...)
```

**DB 2 — SQLite (agent local state):**
```
Path: agent_state.db (AGENT_DB_PATH setting)
Tables:
  - recommendation_log  (rate limit: max 1/room/30s)
  - execution_log       (cooldown 60s + daily cap 50/room)
```

### Ingestion mechanism (`app/script/ingest.py`):
- Script quét `campus_knowledge/` (Markdown files)
- Chunk 500 chars, overlap 100
- Tạo embeddings → insert vào `agent_memory.campus_documents`
- **→ Seeder v2 sẽ cần insert vào cùng bảng này** (hoặc bảng riêng với schema_prefix `benchmark_v2`)

### [XM-6] Cô lập DB — QĐ-9:
- PostgreSQL URL đọc từ `settings.DATABASE_URL`
- **Không có readonly role** trong code hiện tại
- **Options cho Phase B4:**
  - Option A: Tạo PostgreSQL role `benchmark_reader` với GRANT SELECT only
  - Option B: Dùng schema prefix riêng (`benchmark_v2_seed.*`)
  - Option C: Dùng Docker volume riêng (PostgreSQL container clone)
- **→ Cần user quyết định tại G0 (QĐ-9)**

---

## A2.7 — /evaluate Endpoint Schema

**Nguồn:** `app/api/evaluate.py`, `app/schemas/events.py`

### Payload format được nhận:

```python
# Format lồng nhau (ưu tiên):
{
  "event": {
    "room_id": "...",
    "event_type": "...",
    "timestamp": "...",
    "event_data": {"description": "...", ...},
    "operational_context": {...}
  },
  "operational_context": {...}  # optional override
}

# Format phẳng (fallback):
{
  "room_id": "...",
  "event_type": "...",
  ...
}
```

### [XM-7] reference_time support:
- **KHÔNG có** `reference_time` field trong EventPayload hiện tại
- Cần thêm field này vào schema cho v2 (Phase B2)
- Đây là **feature flag** mặc định OFF: `ENABLE_REFERENCE_TIME=False`

---

## Tóm tắt [XM] items — Kết quả

| Item | Câu hỏi | Kết quả |
|------|---------|---------|
| XM-1 | RAG tool implementations | `gateway/rag.py` → `RagClient` + `execute_rag_tool()`. Search qua pgvector, GET/POST tới `/tool/reasoning/*`. Fallback về mock khi `USE_MOCK_RAG=True` hoặc lỗi. |
| XM-2 | Now() / reference_time | `datetime.now(timezone.utc)` hardcoded trong `get_telemetry` và `get_predictions`. **Không có reference_time.** Cần thêm ở Phase B2. |
| XM-3 | Fallback disable flag | **Không tồn tại.** Fallback = try/except trong orchestrator. Cần feature flag `BENCHMARK_MODE` hoặc seeded DB đủ data. Model v1: **`gemini-3.6-flash`**. |
| XM-4 | Tool registry đầy đủ | 7 RAG + 6 Action + 1 Finish. Chi tiết trong A2.1. |
| XM-5 | Trajectory structure | `TrajectoryStep` + `StructuredTraceStep` + `tool_calls_log`. Tối đa 6 steps/round × 3 rounds. RAG budget: 4 calls/evaluate (state), max 5 (settings). |
| XM-6 | DB connection config | PostgreSQL: `postgresql+asyncpg://smartcampus:***@localhost:5432/smartcampus`. SQLite: `agent_state.db`. Không có readonly role. |
| XM-7 | /evaluate payload & reference_time | Schema EventPayload. **Không hỗ trợ reference_time.** |

---

## Câu hỏi chờ quyết định tại G0

| QĐ | Câu hỏi |
|----|---------|
| QĐ-6 (cũ QĐ-7) | k (số lần lặp) và temperature cho mỗi testcase? |
| QĐ-7 (cũ QĐ-8) | Cơ chế neo `reference_time`: thêm vào EventPayload? OperationalContext? Hay mock RAG executor? |
| QĐ-8 (cũ QĐ-9) | Tool đọc nào (RAG) cho phép trong DS testcases? `get_attendance` và `get_schedule` có thể xem canary không? |
| QĐ-9 (cũ QĐ-10) | Cô lập DB: role riêng, schema prefix, hay Docker clone? |
