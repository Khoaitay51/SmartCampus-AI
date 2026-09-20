# 🏫 SmartCampus-AI Agent & Tool Mock System

Hệ thống **SmartCampus AI Agent** tự động giám sát telemetry phòng học, hỗ trợ suy luận ReAct (Observe → Think → Act), đánh giá lại bằng Review/Reflect Agent và kiểm soát an toàn điều khiển thiết bị thông qua **Ma trận phân quyền FSM (Room Mode Permissions)**.

Dự án đã tích hợp sẵn **Bộ Tool Mock (Giả lập)** cho toàn bộ RAG Tools và Action Tools để phát triển, kiểm thử và chạy thử nghiệm mà không phụ thuộc vào hệ thống Backend/Gateway vật lý.

---

## 🛠️ 1. Danh sách Tool & Thông số Tham số

### ⚡ Action Tools (Công cụ điều khiển thiết bị)

| Tool Name | Params | Mô tả |
| :--- | :--- | :--- |
| `set_fan` | `room_id: uuid`, `state: "on" \| "off"` | Bật/tắt quạt thông gió/làm mát |
| `set_door` | `room_id: uuid`, `state: "locked" \| "unlocked"` | Lock/unlock cửa phòng học |
| `set_mode` | `room_id: uuid`, `mode: string` | Chuyển chế độ vận hành phòng học (FSM Mode) |
| `trigger_buzzer` | `room_id: uuid`, `pattern: "short" \| "long" \| "double" \| "emergency"` | Kêu còi báo động (buzzer) |
| `send_alert` | `room_id: uuid`, `message: string` | Gửi notification cảnh báo lên DTwin Dashboard |
| `set_led` | `room_id: uuid`, `color: string`, `effect: "solid" \| "blink"` | Đổi màu/hiệu ứng trên LED strip |

### 🔍 RAG Tools (Công cụ tra cứu dữ liệu - Read Only)

| Tool Name | Params | Mô tả |
| :--- | :--- | :--- |
| `search_history` | `query: string`, `room_id?: string`, `time_range: "1h" \| "6h" \| "24h" \| "7d"` | Tìm kiếm ngữ nghĩa trên dữ liệu tóm tắt lịch sử |
| `get_telemetry` | `room_id: string`, `metric: "temperature" \| "humidity" \| "co2" \| "smoke" \| "occupancy"`, `window: "15m" \| "1h" \| "6h"` | Truy vấn chuỗi thời gian telemetry |
| `get_attendance` | `room_id?: string`, `session_id?: string`, `class_code?: string` | Tra cứu điểm danh theo lớp/buổi học |
| `compare_rooms` | `room_ids: list[string]`, `metric: string`, `window: "1h" \| "6h" \| "24h"` | So sánh chỉ số giữa nhiều phòng |
| `get_room_history` | `room_id: string`, `hours: int` | Tra cứu lịch sử chuyển trạng thái FSM phòng |
| `get_schedule` | `room_id?: string`, `date?: YYYY-MM-DD` | Truy vấn thời khóa biểu / lịch học |
| `get_predictions` | `room_id: string`, `metric: "temperature" \| "co2"`, `horizon: "15m" \| "30m"` | Dự báo chỉ số môi trường bằng EWMA |

---

## 🔒 2. Ma trận Phân quyền Tool theo Room Mode

Agent tuân thủ chặt chẽ ma trận phân quyền sau đây khi đưa ra đề xuất điều khiển thiết bị:

| Tool | SAVING | SELF_STUDY | LECTURE | EXAM | LOCK | SUSPECTED | EMERGENCY |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `set_fan` | **Yes** | **Yes** | **Yes** | **Yes** | No | **Yes** | No |
| `set_door` | **Yes** | **Yes** | **Yes** | No\* | No | **Yes** | **Yes** |
| `set_mode` | **Yes** | **Yes** | **Yes** | **Yes** | No | No | No |
| `trigger_buzzer` | **Yes** | **Yes** | **Yes** | **Yes** | No | **Yes** | **Yes** |
| `send_alert` | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| `set_led` | **Yes** | **Yes** | **Yes** | **Yes** | No | No | No |
| **RAG tools** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| **Getting Metadata**| **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

> **Ghi chú (`No*`):** Trong chế độ phòng thi (`EXAM`), hệ thống cấm mở khóa cửa (`set_door`) để đảm bảo tính bảo mật bài thi. Trong chế độ `EMERGENCY`, hệ thống cho phép mở cửa, kêu buzzer và gửi cảnh báo khẩn cấp.

---

## 🚀 3. Hướng dẫn Cài đặt & Chạy Thử nghiệm

### Bước 1: Cài đặt Môi trường Python

Yêu cầu Python version >= 3.10.

```bash
# Tạo môi trường ảo (tùy chọn)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
```

### Bước 2: Cấu hình File Môi trường `.env`

Tạo file `.env` từ `.env.example`:

```bash
cp .env.example .env
```

Nội dung cơ bản file `.env`:
```env
GEMINI_API_KEY=your-gemini-api-key-here
AGENT=gemini-2.5-flash
BACKEND_BASE_URL=http://localhost:8000/api
EVALUATE_TIMEOUT_SECONDS=25
MAX_REACT_STEP=6
CONFIDENCE_THRESHOLD=0.5
```

---

## 🏃 4. Các Cách Chạy Thử Nghiệm System

### 🔹 Cách 1: Chạy Kịch bản Demo Nhanh (`demo_evaluate.py`)

Chạy demo mô phỏng 2 kịch bản sự kiện (Quá nhiệt phòng học & Phát hiện khói khẩn cấp):

```bash
python demo_evaluate.py
```

*Kết quả đầu ra sẽ hiển thị chi tiết:*
- Phân tích của Agent (Observe → Think → Act).
- Khuyến nghị Tool & Tham số đề xuất.
- Phản hồi giả lập từ Mock Action Tool lên hệ thống DTwin.

---

### 🔹 Cách 2: Chạy FastAPI Server (Bao gồm Mock Gateway DTwin)

Khởi chạy ứng dụng Web API:

```bash
uvicorn app.main:app --reload --port 8000
```

Sau khi khởi chạy:
- Swagger Documentation UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check Endpoint: `GET http://localhost:8000/health`

#### Test Endpoint `/evaluate` qua cURL:

```bash
curl -X POST "http://localhost:8000/evaluate" \
     -H "Content-Type: application/json" \
     -d '{
       "event_id": "c1a01b22-8b9a-4e2b-a010-9b3781294821",
       "event_type": "temperature_anomaly",
       "room_id": "8f2194b1-091a-4c22-b011-897103194822",
       "timestamp": "2026-09-15T09:30:00Z",
       "event_data": {"measured_temp": 33.0},
       "operational_context": {
         "room": {
           "room_id": "8f2194b1-091a-4c22-b011-897103194822",
           "room_name": "Phòng A101",
           "room_type": "lecture_hall",
           "current_mode": "LECTURE",
           "smoke_state": "normal"
         },
         "telemetry_summary": {
           "window_start": "2026-09-15T08:30:00Z",
           "window_end": "2026-09-15T09:30:00Z",
           "temperature": {"min": 24.0, "max": 33.0, "avg": 28.5, "latest": 33.0},
           "humidity": {"min": 50.0, "max": 65.0, "avg": 58.0, "latest": 62.0},
           "co2": {"min": 400.0, "max": 800.0, "avg": 620.0, "latest": 750.0},
           "smoke_value": {"min": 0.0, "max": 0.02, "avg": 0.01, "latest": 0.01},
           "air_quality": {"min": 80.0, "max": 95.0, "avg": 88.0, "latest": 85.0}
         },
         "occupancy": {
           "current_count": 40,
           "total_in": 45,
           "total_out": 5,
           "trend": "phong hoc"
         },
         "recent_events": []
       }
     }'
```

---

### 🔹 Cách 3: Chạy Bộ Kiểm Thử Tự Động (Unit & Integration Tests)

Chạy bộ test case kiểm tra toàn bộ RAG Tools, Action Tools, Mock Gateway và ma trận phân quyền:

```bash
python -m unittest discover -s tests
```

---

## 📁 5. Cấu trúc Thư mục Dự án

```text
SmartCampus-AI/
├── app/
│   ├── agent/             # Logic ReAct, Review Agent, Reflect Agent, Output Parsers
│   ├── api/               # Router FastAPI (/evaluate)
│   ├── config/            # Settings & pydantic-settings
│   ├── gateway/           # Wrapper kết nối Gemini LLM, RAG Client & DTwin Gateway
│   ├── logging/           # Audit trail logging (lưu file JSON kết quả)
│   ├── safety/            # Ma trận phân quyền & kiểm tra an toàn FSM
│   ├── schemas/           # Pydantic schemas cho Context, Events, Recommendations
│   ├── tools/
│   │   └── registry.py    # Khai báo RAG_TOOLS, ACTION_TOOLS, & MODE_PERMISSIONS
│   └── main.py            # Entry point FastAPI Web Server
├── tests/
│   ├── test_call_tool.py  # Unit test cho RAG & Action Tools + Permssion Matrix
│   └── test_evaluate.py   # Test suite cho Agent /evaluate endpoint
├── demo_evaluate.py       # Script kịch bản demo chạy nhanh độc lập
├── requirements.txt       # Danh sách dependencies
├── .env.example           # File mẫu biến môi trường
└── README.md              # Hướng dẫn sử dụng dự án
```
