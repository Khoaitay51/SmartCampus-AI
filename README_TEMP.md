# 🎓 SmartCampus AI Agent (Temporary Progress & Handover README)

> **Tài liệu tạm thời (Temporary README)** dành cho các thành viên trong nhóm để nắm bắt tiến độ dự án, hiểu nhanh kiến trúc đã xây dựng và phân chia công việc phát triển tiếp theo mà không làm ảnh hưởng đến file `README.md` gốc.

---

## 📌 1. BẢNG TIẾN ĐỘ & PHÂN CHIA CÔNG VIỆC (TEAM PROGRESS TRACKER)

| Phân Hệ / Module | Trạng Thái | Mô Tả & Chi Tiết Kỹ Thuật | Ghi Chú / Phụ Trách |
| :--- | :---: | :--- | :--- |
| **Dọn dẹp Codebase** | ✅ Hoàn thành | Xóa bỏ 28 file duplicate lồng nhau trong `app/`, dọn 48 file audit rác, giảm **-2,595 LOC** (-18%). | Toàn bộ mã nguồn đã tinh gọn |
| **ReAct Xen Agent Loop** | ✅ Hoàn thành | Vòng lặp suy luận ReAct 4 bước, tự động gọi công cụ RAG, cơ chế Fallback 4 tầng và Audit Log. | [app/agent/](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/) |
| **Bộ Quy Chuẩn Vận Hành SOP** | ✅ Hoàn thành | 4 tài liệu SOP chuẩn tại [campus_knowledge/](file:///home/user_kma_chinh/SmartCampus-AI/campus_knowledge/): PCCC, Nhiệt độ/HVAC, Phòng thi, An ninh RFID. | Giữ nguyên 100% `prompts.py` |
| **Database & Hybrid Search** | ✅ Hoàn thành | PostgreSQL 16 + pgvector. Hỗ trợ FTS (`tsv tsvector` + GIN index) và Vector Cosine (`embedding vector(768)` + HNSW). | [app/database/models.py](file:///home/user_kma_chinh/SmartCampus-AI/app/database/models.py) |
| **Knowledge Ingestion Script** | ✅ Hoàn thành | Script [app/script/ingest.py](file:///home/user_kma_chinh/SmartCampus-AI/app/script/ingest.py) tự động quét SOP, chunking 500 từ và nạp vector vào DB. | Dùng model `nomic-embed-text` |
| **Edge Context Rollup Service** | ✅ Hoàn thành | Kết nối Edge `GET /tool/reasoning/summaries`. Gom dữ liệu 3 cấp (hourly ➔ daily ➔ weekly) qua `asyncio.to_thread`. | [app/memory/context_rollup.py](file:///home/user_kma_chinh/SmartCampus-AI/app/memory/context_rollup.py) |
| **RAG Tools Unified Retrieval** | ✅ Hoàn thành | Nâng cấp `search_history` và `get_room_history` truy xuất trực tiếp pgvector, giữ nguyên chuẩn **7 Tools**. | 21/21 Unit Tests Pass 100% |
| **Docker Local Compose Stack** | 🟡 Đang test | Cấu hình [docker-compose.yml](file:///home/user_kma_chinh/SmartCampus-AI/docker-compose.yml) gồm `db` (pgvector), `ollama` (qwen2:1.5b), `ollama-init`, `ai-service`. | Cần test thực tế cùng Docker daemon |
| **Tích hợp End-to-End với Edge** | 📋 Cần làm tiếp | Kết nối thông suốt giữa Edge Server (Port 8000) và AI Service (Port 8001) qua mạng nội bộ/Docker network. | **Task tiếp theo cho team** |
| **Frontend Alert Dashboard** | 📋 Cần làm tiếp | Giao diện Web hiển thị trạng thái phòng, nhận cảnh báo thời gian thực từ AI Service qua WebSocket / SSE. | **Task tiếp theo cho team** |
| **Mở rộng SOP Campus mới** | 📋 Cần làm tiếp | Viết thêm các tài liệu SOP cho quản lý mượn thiết bị phòng lab, sự kiện lớn, tiết kiệm điện cuối tuần. | **Task tiếp theo cho team** |

---

## 🏛️ 2. BỨC TRANH KIẾN TRÚC TOÀN CẢNH

```mermaid
flowchart TD
    subgraph IoT_Layer["1. Cảm Biến & Thiết Bị IoT"]
        Sensors[MQ2, DHT22, CO2, RFID, Door] --> ESP32[ESP32 / NodeMCU]
        ESP32 -->|MQTT Telemetry| Broker[Mosquitto Broker]
        Actuators[Quạt, Điều Hòa, Khóa Cửa, Còi] <--|MQTT Command| Broker
    end

    subgraph Edge_Gateway["2. Backend Server & Edge Gateway (Port 8000)"]
        Broker --> MQTTWorker[MQTT Ingestion]
        MQTTWorker --> EdgeRouter[FastAPI Edge Gateway]
        EdgeRouter -->|GET /tool/reasoning/summaries| RollupService[Context Rollup Worker]
    end

    subgraph AI_Engine["3. SmartCampus AI Engine (Port 8001)"]
        EdgeRouter -->|POST /api/evaluate| EvalAPI[app/api/evaluate.py]
        EvalAPI --> AgentCore[ReActXenAgent Loop]
        
        subgraph Reasoning_Memory["ReAct + Hybrid Memory (pgvector)"]
            AgentCore -->|RAG Tool: search_history| RAGClient[app/gateway/rag.py]
            RAGClient -->|Vector Similarity| CampusDocs[(CampusKnowledgeDocument: SOPs)]
            RAGClient -->|Vector Similarity| ContextLogs[(ContextualMemoryLog: Hourly/Daily)]
            RollupService -->|Nạp tóm tắt bối cảnh| ContextLogs
        end
    end

    AgentCore -->|AgentResponse: Control Actions| EdgeRouter
    EdgeRouter -->|Publish Điều Khiển| Broker
```

---

## 📂 3. CẤU TRÚC THƯ MỤC DỰ ÁN ĐÃ TINH GỌN

```text
SmartCampus-AI/
├── app/
│   ├── agent/                 # Động cơ ReAct Xen Agent & Prompts
│   │   ├── prompts.py         # System Prompt cốt lõi (GIỮ NGUYÊN 100%)
│   │   └── react.py           # Vòng lặp suy luận ReAct
│   ├── api/                   # Router FastAPI
│   │   └── evaluate.py        # Endpoint POST /api/evaluate tiếp nhận sự kiện IoT
│   ├── config/                # Cấu hình hệ thống pydantic-settings
│   ├── database/              # Quản lý Database & ORM
│   │   ├── models.py          # CampusKnowledgeDocument & ContextualMemoryLog
│   │   └── session.py         # Async SQLAlchemy engine
│   ├── fallback/              # Cơ chế phòng vệ 4 tầng khi LLM gặp sự cố
│   ├── gateway/               # Giao tiếp ngoại vi (Edge Gateway, RAG, Ollama)
│   │   ├── rag.py             # RagClient & vector retrieval queries
│   │   └── rooms.py           # RoomsClient giao tiếp với Edge
│   ├── llm/                   # Quản lý model LLM & Embedding (Ollama/Gemini)
│   │   └── ollama.py          # Client gọi Ollama & hàm get_embedding
│   ├── logging/               # Hệ thống Audit Log (JSON + Database)
│   ├── memory/                # Trí nhớ dài hạn & Background Rollup Worker
│   │   └── context_rollup.py  # Worker tóm tắt bối cảnh nền (asyncio.to_thread)
│   ├── schemas/               # Hợp đồng dữ liệu Pydantic
│   ├── script/                # Tiện ích vận hành
│   │   └── ingest.py          # Script nạp SOP vào Vector DB
│   ├── tools/                 # Danh mục 7 RAG Tools của Agent
│   │   └── registry.py        # Định nghĩa & ngân sách RAG Tools
│   └── main.py                # Entrypoint FastAPI với Lifespan manager
├── campus_knowledge/          # Kho tri thức tĩnh SOP vận hành khu học xá
│   ├── sop_01_smoke_fire_safety.md
│   ├── sop_02_temperature_hvac_control.md
│   ├── sop_03_occupancy_exam_policy.md
│   └── sop_04_rfid_security_access.md
├── init-db/                   # DDL khởi tạo PostgreSQL pgvector ban đầu
│   └── 01-init.sql
├── tests/                     # Toàn bộ test suite tự động (Unit & Integration)
├── docker-compose.yml         # Khởi chạy pgvector + Ollama + AI Service
├── requirements.txt           # Dependencies Python
├── README.md                  # Tài liệu README gốc của dự án
└── README_TEMP.md             # Tài liệu này (tiến độ & bàn giao)
```

---

## 🚀 4. HƯỚNG DẪN CÀI ĐẶT & CHẠY LOCAL DÀNH CHO BẠN BÈ / TEAM

### Bước 1: Chuẩn Bị Môi Trường Python

Khuyến nghị sử dụng **Python 3.10+**:
```bash
# Tạo môi trường ảo
python3 -m venv .venv

# Kích hoạt môi trường ảo
# Trên Linux/macOS:
source .venv/bin/activate
# Trên Windows:
.venv\Scripts\activate

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt
```

### Bước 2: Thiết Lập File Cấu Hình (.env)

Sao chép từ file mẫu:
```bash
cp .env.example .env
```

Các biến môi trường chính:
```env
# URL kết nối tới Edge Server Gateway
GATEWAY_URL=http://localhost:8000/api

# Cấu hình PostgreSQL pgvector
DATABASE_URL=postgresql+asyncpg://smartcampus:change-this-local-password@localhost:5432/smartcampus

# Cấu hình Ollama Local
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2:1.5b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Chế độ Mock cho test độc lập (không cần backend thật)
USE_MOCK_RAG=true
```

### Bước 3: Khởi Động Hạ Tầng Docker (PostgreSQL pgvector + Ollama)

```bash
docker compose up -d db ollama ollama-init
```
> `ollama-init` sẽ tự động kéo 2 model: `qwen2:1.5b` (suy luận nhẹ) và `nomic-embed-text` (sinh vector 768 chiều).

### Bước 4: Nạp Tài Liệu SOP Vào Vector Database

Sau khi Database và Ollama đã sẵn sàng, nạp toàn bộ tri thức trong `campus_knowledge/`:
```bash
python -m app.script.ingest
```

### Bước 5: Chạy AI Service

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```
- Swagger API Docs: `http://localhost:8001/docs`
- Healthcheck Endpoint: `http://localhost:8001/health`

### Bước 6: Chạy Bộ Kiểm Thử (Unit Tests)

```bash
USE_MOCK_RAG=true python -m unittest discover tests
```
*(Hiện tại 21/21 tests đều đã PASS 100%).*

---

## ⚠️ 5. BA NGUYÊN TẮC CẦN NHỚ KHI PHÁT TRIỂN TIẾP (CRITICAL RULES)

1. **Tuyệt đối KHÔNG sửa file `app/agent/prompts.py`**:
   - Mọi quy định mới về phòng thi, cháy nổ, kiểm soát ra vào đều phải được viết thành file Markdown trong thư mục `campus_knowledge/` rồi nạp qua RAG, **không** nhồi trực tiếp vào System Prompt.
2. **Bảo toàn chuẩn 7 RAG Tools**:
   - Agent được ràng buộc chặt chẽ với đúng **7 công cụ RAG** (`RAG_TOOLS` trong `app/tools/registry.py`) và ngân sách tối đa 5 lượt gọi (`RagCallBudget`).
   - Tuyệt đối không tự ý khai báo thêm tool mới (như `search_sop`) vì sẽ làm vỡ Unit Test và làm Agent phân tâm/cạn ngân sách gọi tool. Mọi nhu cầu tra cứu ngữ nghĩa đều được hợp nhất vào `search_history` và `get_room_history`.
3. **Không làm nghẽn Event Loop của FastAPI**:
   - Bất kỳ tác vụ CPU-bound nào (tính toán số liệu thống kê, nén tóm tắt, gọi model đồng bộ) trong background worker bắt buộc phải được bao bọc bằng `asyncio.to_thread`.

---

## 📖 6. CÁC TÀI LIỆU CHI TIẾT ĐỂ ĐỌC THÊM
- [SYSTEM_WALKTHROUGH.md](file:///home/user_kma_chinh/SmartCampus-AI/SYSTEM_WALKTHROUGH.md): Phân tích chi tiết toàn bộ kiến trúc ReAct, cơ chế Fallback, và mô hình dữ liệu.
- [recent_changes_walkthrough.md](file:///home/user_kma_chinh/.gemini/antigravity-ide/brain/4d164a70-8e5b-4cf0-a953-be96174878ea/recent_changes_walkthrough.md): Nhật ký chi tiết toàn bộ các hạng mục cải tiến vừa thực hiện trong phiên làm việc này.
