# HƯỚNG DẪN KIẾN TRÚC TOÀN DIỆN HỆ THỐNG SMARTCAMPUS-AI
> **Tài liệu Walkthrough, Phân tích Mã nguồn & Lộ trình Triển khai RAG + Backend API**

---

## MỤC LỤC
1. [Bức Tranh Tổng Thể (The Big Picture)](#1-bức-tranh-tổng-thể-the-big-picture)
2. [Hạ Tầng Docker & Mô Hình AI Cục Bộ (pgvector + Ollama)](#2-hạ-tầng-docker--mô-hình-ai-cục-bộ-pgvector--ollama)
3. [Bản Đồ Thư Mục & Vai Trò Mã Nguồn](#3-bản-đồ-thư-mục--vai-trò-mã-nguồn)
4. [Vòng Đời Xử Lý Sự Kiện (Data Lifecycle)](#4-vòng-đời-xử-lý-sự-kiện-data-lifecycle)
5. [Mổ Xẻ Chi Tiết Từng Module Cốt Lõi](#5-mổ-xẻ-chi-tiết-từng-module-cốt-lõi)
   - [5.1. Schemas & Hợp đồng Dữ liệu (`app/schemas/`)](#51-schemas--hợp-đồng-dữ-liệu-appschemas)
   - [5.2. Động cơ ReAct Xen Agent (`app/agent/`)](#52-động-cơ-react-xen-agent-appagent)
   - [5.3. Tầng LLM & Embedding (`app/llm/` & `app/gateway/embeddings.py`)](#53-tầng-llm--embedding-appllm--appgatewayembeddingspy)
   - [5.4. Cơ sở Dữ liệu & Long-Term Memory (`app/database/`)](#54-cơ-sở-dữ-liệu--long-term-memory-appdatabase)
   - [5.5. RAG Gateway & Tools Registry (`app/gateway/` & `app/tools/`)](#55-rag-gateway--tools-registry-appgateway--apptools)
   - [5.6. Hệ thống Phòng thủ Fallback 4 Cấp (`app/fallback/`)](#56-hệ-thống-phòng-thủ-fallback-4-cấp-appfallback)
   - [5.7. Logging & Giám sát (`app/logging/`)](#57-logging--giám-sát-applogging)
6. [Hướng Dẫn Triển Khai RAG Pipeline Hoàn Chỉnh](#6-hướng-dẫn-triển-khai-rag-pipeline-hoàn-chỉnh)
7. [Hướng Dẫn Thiết Kế Backend API (RBAC, JWT, WebSocket, MQTT)](#7-hướng-dẫn-thiết-kế-backend-api-rbac-jwt-websocket-mqtt)
8. [Sổ Tay Lệnh Vận Hành & Kiểm Thử](#8-sổ-tay-lệnh-vận-hành--kiểm-thử)

---

## 1. Bức Tranh Tổng Thể (The Big Picture)

**SmartCampus-AI** đóng vai trò là khối não bộ biên (**Edge AI Decision Engine**) cho khu học xá thông minh. Nhiệm vụ trung tâm của dịch vụ:
1. Tiếp nhận dữ liệu quan trắc thời gian thực từ mạng lưới cảm biến IoT (khói, nhiệt độ, độ ẩm, CO2, RFID quẹt thẻ, trạng thái đóng/mở cửa).
2. Kết hợp dữ liệu cảm biến với bối cảnh vận hành phòng học (phòng đang giảng dạy, phòng tự học, hay đang thi cử).
3. Kích hoạt động cơ **ReAct (Reasoning + Acting)**: tự suy luận, tự gọi các công cụ tra cứu **RAG** để bổ sung thông tin.
4. Tự tra cứu kinh nghiệm tương tự trong quá khứ thông qua **Vector Long-Term Memory (pgvector)** làm mẫu học nhanh (Dynamic Few-Shot).
5. Tự rà soát kiểm tra an toàn theo ma trận phân quyền chế độ phòng trước khi ra lệnh điều khiển thiết bị phần cứng (bật quạt, đóng/mở cửa, kích hoạt còi, gửi cảnh báo).

```mermaid
flowchart TD
    subgraph Hardware_IoT["1. Thiết Bị Ngoại Vi (IoT Edge)"]
        Sensors[Cảm biến: MQ2, DHT22, CO2, RFID, Door] --> ESP32[ESP32 / NodeMCU]
        ESP32 -->|MQTT Telemetry| Broker[MQTT Broker Mosquitto]
        Actuators[Quạt, Cửa khóa, Còi Buzzer, Đèn LED] <--|MQTT Command| Broker
    end

    subgraph Backend_Gateway["2. Backend Server & Edge Gateway (Port 8000)"]
        Broker --> MQTTWorker[MQTT Ingestion Worker]
        MQTTWorker --> EdgeRouter[FastAPI Gateway API]
        AdminApp[Dashboard Giảng viên / Quản trị] -->|WebSocket Alerts & REST JWT| EdgeRouter
    end

    subgraph AI_Engine["3. SmartCampus AI Engine (Port 8001)"]
        EdgeRouter -->|POST /api/evaluate| EvalAPI[app/api/evaluate.py]
        EvalAPI --> EnrichContext[Enrich Raw Telemetry Context]
        EnrichContext --> AgentCore[ReActXenAgent Loop]

        subgraph Reasoning_Loop["Vòng Lặp ReAct + LTM"]
            AgentCore --> DynamicFewShot[Truy vấn LTM: retrieve_past_experience]
            DynamicFewShot --> LLMCall[Ollama Qwen2:1.5b SLM / Gemini]
            LLMCall --> OutputParse[Thought - Action - Action Input]
            OutputParse --> ToolRouter{Action Type}
            ToolRouter -->|RAG Tool| RAGExecute[app/gateway/rag.py]
            RAGExecute -->|Observation| LLMCall
            ToolRouter -->|Finish Tool| SelfReview[Self-Review & Reflection]
        end

        subgraph Memory_Layer["Lưu Trữ & Phòng Vệ"]
            SelfReview --> AuditWrite[app/logging/audit.py]
            AuditWrite --> PGVector[(PostgreSQL 16 + pgvector)]
            AuditWrite --> AuditFiles[JSON Audit Files ./output/]
            SelfReview --> FallbackOrch[Fallback Orchestrator 4-Tiers]
        end
    end

    AgentCore -->|AgentResponse: Control Actions| EdgeRouter
    EdgeRouter -->|Publish Actuator Topics| Broker
```

---

## 2. Hạ Tầng Docker & Mô Hình AI Cục Bộ (pgvector + Ollama)

File cấu hình chính: [docker-compose.yml](file:///home/user_kma_chinh/SmartCampus-AI/docker-compose.yml)

### Các Container Chạy Trong Hệ Thống:

1. **`db` (`pgvector/pgvector:pg16`)**:
   - Thay thế PostgreSQL truyền thống bằng image có sẵn extension vector.
   - Khi khởi động lần đầu, Postgres tự thực thi script [init-db/01-init.sql](file:///home/user_kma_chinh/SmartCampus-AI/init-db/01-init.sql):
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     CREATE SCHEMA IF NOT EXISTS agent_memory;
     GRANT ALL PRIVILEGES ON SCHEMA agent_memory TO smartcampus;
     ```
   - Dữ liệu lưu vĩnh viễn trong volume `pgvector_data`.
   - Có healthcheck kiểm tra `pg_isready` trước khi cho phép AI Service kết nối.

2. **`ollama` (`ollama/ollama:latest`)**:
   - Chạy engine suy luận LLM & Embedding cục bộ, không phụ thuộc vào internet hoặc quota API cloud.
   - Mở port `11434` ra máy chủ, lưu model trong volume `ollama_data`.
   - Có healthcheck kiểm tra lệnh `ollama list`.
   - Hỗ trợ cắm GPU NVIDIA khi uncomment khối `deploy.resources.reservations`.

3. **`ollama-init` (Auto-pull Bootstrap Service)**:
   - Chờ `ollama` container chuyển sang trạng thái `healthy`.
   - Tự động thực thi lệnh pull 2 models cần thiết:
     - `nomic-embed-text`: Model sinh vector embedding chuyên biệt, độ dài chuẩn **768 chiều**, tối ưu cho ngữ nghĩa tiếng Anh & tiếng Việt.
     - `qwen2:1.5b`: Model Small Language Model (SLM) ~1.5 tỷ tham số của Alibaba Cloud. Kích thước chỉ ~934MB, suy luận cực nhanh trên CPU và tuân thủ định dạng Tool-calling tốt.
   - Hoàn tất xong container sẽ tự thoát (Exit code 0).

4. **`ai-agent` (FastAPI Service)**:
   - Build từ [Dockerfile](file:///home/user_kma_chinh/SmartCampus-AI/Dockerfile).
   - Phụ thuộc (`depends_on`) vào cả `db` và `ollama` (chỉ chạy khi cả hai đã `healthy`).
   - Mở port `8001:8000`. Mount mã nguồn để hỗ trợ hot-reload (`--reload`).

---

## 3. Bản Đồ Thư Mục & Vai Trò Mã Nguồn

| Đường Dẫn | Vai Trò Chính |
| :--- | :--- |
| [docker-compose.yml](file:///home/user_kma_chinh/SmartCampus-AI/docker-compose.yml) | Cấu hình toàn bộ cụm container (pgvector, ollama, ollama-init, ai-agent) |
| [init-db/01-init.sql](file:///home/user_kma_chinh/SmartCampus-AI/init-db/01-init.sql) | Script kích hoạt `vector` extension & schema `agent_memory` |
| [.env](file:///home/user_kma_chinh/SmartCampus-AI/.env) | File biến môi trường runtime |
| [.env.example](file:///home/user_kma_chinh/SmartCampus-AI/.env.example) | Mẫu biến môi trường chuẩn |
| [app/main.py](file:///home/user_kma_chinh/SmartCampus-AI/app/main.py) | Điểm khởi đầu FastAPI, gắn router `health`, `evaluate`, `feedback` |
| [app/config/settings.py](file:///home/user_kma_chinh/SmartCampus-AI/app/config/settings.py) | Đọc và kiểm thực biến môi trường (Pydantic Settings) |
| [app/schemas/events.py](file:///home/user_kma_chinh/SmartCampus-AI/app/schemas/events.py) | Định nghĩa các dạng sự kiện: khói, nhiệt độ, quẹt thẻ, người |
| [app/schemas/context.py](file:///home/user_kma_chinh/SmartCampus-AI/app/schemas/context.py) | Định nghĩa bối cảnh phòng: telemetry summary, active session, occupancy |
| [app/schemas/recommendation.py](file:///home/user_kma_chinh/SmartCampus-AI/app/schemas/recommendation.py) | Định nghĩa đầu ra của Agent (`AgentResponse`, `ToolRecommendation`) |
| [app/api/evaluate.py](file:///home/user_kma_chinh/SmartCampus-AI/app/api/evaluate.py) | Endpoint `POST /evaluate` tiếp nhận payload sự kiện và điều phối Agent |
| [app/api/feedback.py](file:///home/user_kma_chinh/SmartCampus-AI/app/api/feedback.py) | Endpoint `POST /feedback` tiếp nhận đánh giá của con người (RLHF) |
| [app/agent/agent.py](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/agent.py) | Lớp `ReActXenAgent`, hàm truy vấn bộ nhớ `retrieve_past_experience` |
| [app/agent/loop.py](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/loop.py) | Vòng lặp suy luận ReAct (Thought - Action - Observation) |
| [app/agent/output_parser.py](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/output_parser.py) | Bộ phân tích regex bóc tách lệnh của LLM |
| [app/agent/prompts.py](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/prompts.py) | Định dạng System Prompt, Dynamic Few-shot, Review & Reflect Prompt |
| [app/database/models.py](file:///home/user_kma_chinh/SmartCampus-AI/app/database/models.py) | SQLAlchemy Models: `AgentExperienceLog`, `AgentEnvironmentSnapshot`,... |
| [app/database/session.py](file:///home/user_kma_chinh/SmartCampus-AI/app/database/session.py) | Kết nối asyncpg, tự tạo bảng và chỉ mục IVFFLAT |
| [app/llm/client.py](file:///home/user_kma_chinh/SmartCampus-AI/app/llm/client.py) | Protocol giao tiếp chuẩn `LLMClient` |
| [app/llm/ollama.py](file:///home/user_kma_chinh/SmartCampus-AI/app/llm/ollama.py) | Client gọi mô hình SLM chạy trên Ollama cục bộ |
| [app/llm/gemini.py](file:///home/user_kma_chinh/SmartCampus-AI/app/llm/gemini.py) | Client gọi Google Gemini API |
| [app/gateway/embeddings.py](file:///home/user_kma_chinh/SmartCampus-AI/app/gateway/embeddings.py) | Tạo vector nhúng qua nomic-embed-text (dim 768), cắt đoạn (chunking) |
| [app/gateway/rag.py](file:///home/user_kma_chinh/SmartCampus-AI/app/gateway/rag.py) | Wrapper gọi 7 RAG Tools, giới hạn ngân sách 5 calls, mock fallback |
| [app/gateway/rooms.py](file:///home/user_kma_chinh/SmartCampus-AI/app/gateway/rooms.py) | Client HTTP query thông tin phòng và telemetry từ Gateway |
| [app/tools/registry.py](file:///home/user_kma_chinh/SmartCampus-AI/app/tools/registry.py) | Định nghĩa Action Tools, RAG Tools, Ma trận quyền theo `room_mode` |
| [app/fallback/](file:///home/user_kma_chinh/SmartCampus-AI/app/fallback/) | Hệ thống phòng thủ 4 cấp: Model $\rightarrow$ Parser $\rightarrow$ Tool Mock $\rightarrow$ Heuristic Rules |
| [app/logging/audit.py](file:///home/user_kma_chinh/SmartCampus-AI/app/logging/audit.py) | Ghi audit log ra JSON file và lưu vector LTM vào pgvector |
| [mock_backend.py](file:///home/user_kma_chinh/SmartCampus-AI/mock_backend.py) | Giả lập Gateway API đầy đủ các kịch bản để test không cần DB/IoT thật |
| [run_agent_demo.py](file:///home/user_kma_chinh/SmartCampus-AI/run_agent_demo.py) | Script demo chạy 5 kịch bản thực tế |

---

## 4. Vòng Đời Xử Lý Sự Kiện (Data Lifecycle)

Chi tiết 6 bước xử lý một sự kiện từ Gateway đến khi thiết bị được kích hoạt:

```
[Gateway gửi HTTP POST /api/evaluate]
               │
               ▼
BƯỚC 1: TIẾP NHẬN & BỔ SUNG NGỮ CẢNH (Enrichment)
  - app/api/evaluate.py bóc tách EventPayload & OperationalContext.
  - Gọi enrich_context_with_environment() kéo telemetry thô 5 phút gần nhất từ Edge.
               │
               ▼
BƯỚC 2: TRUY VẤN BỘ NHỚ QUÁ KHỨ (Dynamic Few-Shot)
  - app/agent/agent.py:retrieve_past_experience() nhúng văn bản bối cảnh thành vector 768 chiều.
  - SELECT top 3 case tương tự từ agent_memory.agent_experience_logs với human_approved=True.
  - Bơm các bài học thành công vào System Prompt.
               │
               ▼
BƯỚC 3: VÒNG LẶP SUY LUẬN (ReAct Execution Loop)
  - app/agent/loop.py gửi prompt sang Ollama (qwen2:1.5b) hoặc Gemini.
  - LLM trả về Thought & Action.
  - Nếu Action là RAG Tool (ví dụ: get_predictions, get_room_history):
      + app/gateway/rag.py kiểm tra ngân sách (tối đa 5 lần).
      + Thực thi tool, lấy dữ liệu, biến thành Observation nạp lại vào prompt.
  - Lặp lại tối đa 6 bước cho đến khi LLM ra Action: finish.
               │
               ▼
BƯỚC 4: TỰ PHẢN TỈNH & SỬA SAI (Self-Review & Reflection)
  - Nếu confidence < 0.5 HOẶC tool đề xuất vi phạm ma trận quyền room_mode (ví dụ: đòi bật còi khi đang thi):
      + Bật prompt phản tỉnh yêu cầu LLM tự xem xét lại quyết định.
      + Cho phép sửa lại đề xuất an toàn hơn.
               │
               ▼
BƯỚC 5: PHÒNG VỆ SỰ CỐ (Fallback Orchestration)
  - Nếu LLM sập / quá thời gian 25s:
      + Chuyển xuống Cấp 4 (Rule-based Fallback app/fallback/rules.py).
      + Sử dụng luật heuristic cứng (khói > 400 bật cảnh báo, nhiệt độ > 35°C bật quạt).
               │
               ▼
BƯỚC 6: GHI BỘ NHỚ & TRẢ KẾT QUẢ (Audit & LTM Persistence)
  - app/logging/audit.py:save_audit_and_memory():
      + Ghi JSON file lưu vết kiểm toán tại ./output/.
      + Nhúng câu trả lời và lưu vào pgvector (agent_decision_logs, agent_experience_logs).
  - Trả về AgentResponse chứa ToolRecommendation cho Gateway thực thi thiết bị.
```

---

## 5. Mổ Xẻ Chi Tiết Từng Module Cốt Lõi

### 5.1. Schemas & Hợp đồng Dữ liệu (`app/schemas/`)

Toàn bộ thông điệp được mô hình hóa chặt chẽ qua Pydantic V2:

- **[app/schemas/events.py](file:///home/user_kma_chinh/SmartCampus-AI/app/schemas/events.py)**:
  `EventType` bao gồm:
  - `smoke_detected`: Cảm biến MQ2 phát hiện khói bất thường.
  - `occupancy_change`: Có người ra/vào phòng học.
  - `temperature_anomaly`: Nhiệt độ vượt ngưỡng hoặc tăng dốc.
  - `rfid_unknown`: Thẻ sinh viên/khách lạ quẹt ngoài giờ.
  - `manual_trigger`: Giảng viên hoặc bảo vệ kích hoạt thủ công.

- **[app/schemas/context.py](file:///home/user_kma_chinh/SmartCampus-AI/app/schemas/context.py)**:
  - `RoomInfo`: Tên phòng, loại phòng (`lecture_hall`, `lab`), chế độ phòng (`current_mode`).
  - `TelemetrySummary`: Thống kê `min`, `max`, `avg`, `latest` của nhiệt độ, độ ẩm, CO2, khói, chất lượng không khí.
  - `Occupancy`: Số người hiện tại (`current_count`), vào, ra.
  - `ActiveSession`: Buổi học đang chạy: mã môn, giảng viên, sĩ số, hạn điểm danh, cờ `is_exam`.

- **[app/schemas/recommendation.py](file:///home/user_kma_chinh/SmartCampus-AI/app/schemas/recommendation.py)**:
  - `ToolRecommendation`: Chứa `tool_name`, `tool_params`, `reason`, `confidence` (từ 0.0 đến 1.0), `urgency` (`low`, `medium`, `high`). Có validator `must_be_whitelisted` ngăn cấm việc gọi tool ngoài danh mục.
  - `AgentResponse`: Kết quả trả về cho Gateway. Có factory method `AgentResponse.fallback()` để tạo response chuẩn mực khi rơi vào chế độ dự phòng.

---

### 5.2. Động cơ ReAct Xen Agent (`app/agent/`)

1. **[app/agent/agent.py](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/agent.py)** (`ReActXenAgent`):
   - Hàm `retrieve_past_experience(current_context_text)`: Nhúng bối cảnh hiện tại qua `get_embedding()`, truy vấn bảng `agent_experience_logs` với điều kiện `human_approved == True`, sắp xếp theo `cosine_distance` để lấy 3 kinh nghiệm gần nhất đưa vào prompt làm Dynamic Few-Shot.
2. **[app/agent/loop.py](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/loop.py)** (`ReActLoopRunner`):
   - Quản lý vòng lặp suy luận bước-theo-bước.
   - Giới hạn cứng `MAX_REACT_STEP = 6` và `MAX_RAG_CALLS = 5`.
   - Nếu LLM trả về `Action: finish`, kiểm tra điều kiện kích hoạt Reflection nếu vi phạm quyền hạn hoặc confidence < 0.5.
3. **[app/agent/output_parser.py](file:///home/user_kma_chinh/SmartCampus-AI/app/agent/output_parser.py)**:
   - Dùng biểu thức chính quy (Regex) bóc tách các khối `Thought:`, `Action:`, `Action Input:`.
   - Xử lý các biến thể Markdown codeblock (```json ... ```) để bóc JSON an toàn.

---

### 5.3. Tầng LLM & Embedding (`app/llm/` & `app/gateway/embeddings.py`)

- **[app/llm/client.py](file:///home/user_kma_chinh/SmartCampus-AI/app/llm/client.py)**:
  Định nghĩa `Protocol`:
  ```python
  class LLMClient(Protocol):
      async def complete(self, system_prompt: str) -> str: ...
  ```
- **[app/llm/ollama.py](file:///home/user_kma_chinh/SmartCampus-AI/app/llm/ollama.py)** (`OllamaLLMClient`):
  Kết nối trực tiếp đến endpoint `/api/generate` của Ollama, sử dụng `stop_sequences = ["Observation:", "\nObservation:"]` để dừng đúng thời điểm model muốn thực thi tool.
- **[app/gateway/embeddings.py](file:///home/user_kma_chinh/SmartCampus-AI/app/gateway/embeddings.py)**:
  - `get_embedding(text)`: Gọi Ollama `/api/embed` với model `nomic-embed-text` để lấy vector float 768 chiều.
  - `chunk_text(text, chunk_size=3500, overlap=500)`: Cắt văn bản tài liệu dài thành từng đoạn nhỏ có gối đầu (overlap) để phục vụ lập chỉ mục RAG.

---

### 5.4. Cơ sở Dữ liệu & Long-Term Memory (`app/database/`)

- **[app/database/models.py](file:///home/user_kma_chinh/SmartCampus-AI/app/database/models.py)**:
  - Tất cả các bảng nằm trong schema `agent_memory`.
  - Cột vector được định nghĩa dạng `Vector(settings.EMBEDDING_DIM)` (768 chiều).
  - Bảng `agent_experience_logs`: Lưu vết sự kiện, context embedding, quyết định và nhãn duyệt của con người (`human_approved`, `env_reward`).
  - Bảng `agent_decision_logs`: Lưu toàn bộ chi tiết phân tích của Agent.
- **[app/database/session.py](file:///home/user_kma_chinh/SmartCampus-AI/app/database/session.py)**:
  - Khởi tạo Async Engine với `create_async_engine(settings.DATABASE_URL)`.
  - Tự động khởi tạo Extension và chỉ mục `IVFFLAT` cosine ops (`vector_cosine_ops`).

---

### 5.5. RAG Gateway & Tools Registry (`app/gateway/` & `app/tools/`)

- **[app/tools/registry.py](file:///home/user_kma_chinh/SmartCampus-AI/app/tools/registry.py)**:
  - Phân loại rõ ràng `RAG_TOOLS` (chỉ đọc) và `ACTION_TOOLS` (điều khiển thiết bị).
  - `MODE_PERMISSIONS`: Ma trận phân quyền theo chế độ phòng:
    - Chế độ `EXAM`: Cấm `trigger_buzzer` và `set_door`.
    - Chế độ `LOCK`: Cấm `set_fan`, `set_door`.
    - Chế độ `EMERGENCY`: Toàn quyền can thiệp.
- **[app/gateway/rag.py](file:///home/user_kma_chinh/SmartCampus-AI/app/gateway/rag.py)**:
  - Lớp `RagCallBudget`: Đảm bảo không evaluation nào được gọi quá 5 lần RAG tools.
  - Tích hợp `get_mock_rag_data()` tự động cung cấp dữ liệu giả lập thực tế khi Gateway thật tạm thời không phản hồi.

---

### 5.6. Hệ thống Phòng thủ Fallback 4 Cấp (`app/fallback/`)

Được thiết kế để đảm bảo an toàn tính mạng và tính sẵn sàng 99.99%:
- **Cấp 1 (Model Fallback)** ([app/fallback/llm_fallback.py](file:///home/user_kma_chinh/SmartCampus-AI/app/fallback/llm_fallback.py)): Dùng `CircuitBreaker`. Nếu model chính bị lỗi 429/timeout liên tiếp, tự động chuyển sang model phụ hoặc Ollama local.
- **Cấp 2 (Parser Fallback)** ([app/fallback/parsing.py](file:///home/user_kma_chinh/SmartCampus-AI/app/fallback/parsing.py)): Cố gắng vá lỗi JSON nếu LLM sinh thiếu ngoặc hoặc lỗi định dạng.
- **Cấp 3 (Tool Fallback)** ([app/fallback/tool_fallback.py](file:///home/user_kma_chinh/SmartCampus-AI/app/fallback/tool_fallback.py)): Giả lập kết quả quan trắc nếu Edge Gateway tạm thời ngắt kết nối.
- **Cấp 4 (Rule-based Fallback)** ([app/fallback/rules.py](file:///home/user_kma_chinh/SmartCampus-AI/app/fallback/rules.py)): Chốt chặn cuối cùng bằng luật if/else thuần túy, không dùng LLM, ưu tiên an toàn tính mạng (cháy/khói) lên trên hết.

---

### 5.7. Logging & Giám sát (`app/logging/`)

- **[app/logging/audit.py](file:///home/user_kma_chinh/SmartCampus-AI/app/logging/audit.py)**:
  - Ghi mỗi quyết định thành file JSON kiểm toán tại `./output/{timestamp}_{event_id}.json`.
  - Gọi bất đồng bộ việc lưu trữ vào pgvector. Lỗi ghi DB được cô lập và không làm gián đoạn việc trả kết quả về cho Edge Gateway.
- **[app/logging/observability.py](file:///home/user_kma_chinh/SmartCampus-AI/app/logging/observability.py)**:
  - Cấu hình format logging chuẩn cho môi trường container.

---

## 6. Hướng Dẫn Triển Khai RAG Pipeline Hoàn Chỉnh

Pipeline RAG hoàn chỉnh kết hợp **Ollama (nomic-embed-text)** và **PostgreSQL (pgvector)** được triển khai qua 4 bước:

### Bước 1: Khởi tạo Bảng Tri Thức (Knowledge Store)
Thêm bảng vào database (hoặc script migration alembic):
```sql
CREATE TABLE IF NOT EXISTS agent_memory.campus_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type VARCHAR(50) NOT NULL, -- 'fire_safety_sop', 'lecture_policy', 'device_manual'
    title VARCHAR(255) NOT NULL,
    chunk_content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chỉ mục HNSW cho tốc độ tìm kiếm dưới 3ms
CREATE INDEX IF NOT EXISTS idx_campus_documents_embedding 
ON agent_memory.campus_documents 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Bước 2: Viết Script Nạp Tài Liệu & Tạo Vector
Tạo file `scripts/ingest_knowledge.py`:
```python
import asyncio
from app.database.session import async_session
from app.gateway.embeddings import chunk_text, embed_texts
from sqlalchemy import text

async def ingest_document(title: str, doc_type: str, content: str):
    # 1. Cắt nhỏ tài liệu
    chunks = chunk_text(content, chunk_size=800, overlap=100)
    # 2. Sinh vector embedding qua Ollama nomic-embed-text
    vectors = embed_texts(chunks)
    
    # 3. Lưu vào pgvector
    async with async_session() as db:
        for chunk, vec in zip(chunks, vectors):
            await db.execute(
                text("""
                    INSERT INTO agent_memory.campus_documents (doc_type, title, chunk_content, embedding)
                    VALUES (:doc_type, :title, :chunk, :vec)
                """),
                {"doc_type": doc_type, "title": title, "chunk": chunk, "vec": str(vec)}
            )
        await db.commit()
    print(f"Đã nạp xong tài liệu '{title}' ({len(chunks)} chunks).")
```

### Bước 3: Nối RAG Tool `search_history` vào pgvector
Cập nhật method `search_history` trong [app/gateway/rag.py](file:///home/user_kma_chinh/SmartCampus-AI/app/gateway/rag.py):
```python
async def search_history(self, query: str, room_id: str | None = None, time_range: str = "24h") -> dict[str, Any]:
    self.budget.consume("search_history")
    
    # 1. Trích xuất vector của câu query
    from app.gateway.embeddings import get_embedding
    query_vec = await get_embedding(query)
    
    # 2. Truy vấn Hybrid (Vector similarity + lọc phòng/loại tài liệu)
    from app.database.session import async_session
    from sqlalchemy import text
    
    async with async_session() as db:
        sql = text("""
            SELECT title, chunk_content, 1 - (embedding <=> :vec) AS similarity
            FROM agent_memory.campus_documents
            ORDER BY embedding <=> :vec
            LIMIT 3;
        """)
        res = await db.execute(sql, {"vec": str(query_vec)})
        rows = res.fetchall()
        
    return {
        "query": query,
        "results": [
            {"title": r[0], "content": r[1], "similarity": round(float(r[2]), 3)}
            for r in rows
        ]
    }
```

---

## 7. Hướng Dẫn Thiết Kế Backend API (RBAC, JWT, WebSocket, MQTT)

Sơ đồ kiến trúc tích hợp toàn diện:

```
[Phần Cứng IoT] ──(MQTT Telemetry)──► [MQTT Broker: Mosquitto]
                                              │
                                              ▼
                                    [FastAPI Backend Server]
                                    ├── Auth: JWT + RBAC Middleware
                                    ├── MQTT Worker (Lắng nghe & Ra lệnh)
                                    ├── WebSocket Manager (Push Dashboard)
                                    └── HTTP Client ──► [AI Service: POST /evaluate]
```

### 7.1. Phân Quyền Vai Trò (RBAC) & Xác Thực JWT
Cài đặt thư viện: `pyjwt`, `pwdlib[bcrypt]`.

```python
# app/auth/rbac.py
from enum import Enum
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    LECTURER = "LECTURER"
    SECURITY = "SECURITY"
    STUDENT = "STUDENT"

security = HTTPBearer()
JWT_SECRET = "smartcampus-secret-key-change-in-prod"

def require_roles(*allowed_roles: UserRole):
    async def _checker(creds: HTTPAuthorizationCredentials = Security(security)):
        try:
            payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=["HS256"])
            user_role = payload.get("role")
            if user_role not in [r.value for r in allowed_roles]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Quyền '{user_role}' không được phép thực hiện chức năng này."
                )
            return payload
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã hết hạn.")
    return _checker

# Cách áp dụng trên Router:
# @router.post("/rooms/{room_id}/lock", dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.SECURITY))])
```

---

### 7.2. WebSocket: Streaming Dữ Liệu Thời Gian Thực & Cảnh Báo
Quản lý các kết nối WebSocket phân chia theo phòng học:

```python
# app/websocket/connection_manager.py
from fastapi import WebSocket
from typing import Dict, Set

class RoomWebSocketManager:
    def __init__(self):
        # Lưu socket theo room_id: { "room-a101": {ws1, ws2}, ... }
        self.active_rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.active_rooms.setdefault(room_id, set()).add(ws)

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self.active_rooms:
            self.active_rooms[room_id].discard(ws)

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id in self.active_rooms:
            for ws in list(self.active_rooms[room_id]):
                await ws.send_json(message)

ws_manager = RoomWebSocketManager()

# Router WebSocket:
# @app.websocket("/ws/rooms/{room_id}")
# async def websocket_endpoint(ws: WebSocket, room_id: str):
#     await ws_manager.connect(room_id, ws)
#     try:
#         while True:
#             await ws.receive_text() # giữ kết nối
#     except Exception:
#         ws_manager.disconnect(room_id, ws)
```

---

### 7.3. MQTT: Lắng Nghe Cảm Biến & Điều Khiển Thiết Bị
Cài đặt: `aiomqtt`.

#### Định nghĩa Cây Topic Chuẩn:
- Cảm biến gửi lên: `smartcampus/rooms/{room_id}/sensors/telemetry`
- Lệnh điều khiển gửi xuống: `smartcampus/rooms/{room_id}/actuators/{device}`

```python
# app/mqtt/service.py
import asyncio
import json
import aiomqtt
import httpx
from app.websocket.connection_manager import ws_manager

AI_EVALUATE_URL = "http://localhost:8001/evaluate"

async def run_mqtt_worker():
    async with aiomqtt.Client("localhost", port=1883) as client:
        # Lắng nghe dữ liệu tất cả các phòng
        await client.subscribe("smartcampus/rooms/+/sensors/telemetry")
        
        async for message in client.messages:
            payload = json.loads(message.payload.decode())
            topic_parts = str(message.topic).split("/")
            room_id = topic_parts[2]
            
            # 1. Bắn trực tiếp dữ liệu thô lên Dashboard qua WebSocket
            await ws_manager.broadcast_to_room(room_id, {
                "type": "TELEMETRY_UPDATE",
                "data": payload
            })
            
            # 2. Kiểm tra điều kiện ngưỡng bất thường -> Kích hoạt AI Agent
            if payload.get("temperature", 0) > 33 or payload.get("smoke", 0) > 300:
                async with httpx.AsyncClient() as http:
                    res = await http.post(AI_EVALUATE_URL, json=payload, timeout=25.0)
                    ai_decision = res.json()
                
                # 3. Nếu AI quyết định can thiệp thiết bị:
                if not ai_decision.get("skip") and ai_decision.get("recommendation"):
                    rec = ai_decision["recommendation"]
                    tool_name = rec["tool_name"]   # ví dụ: set_fan
                    params = rec["tool_params"]     # ví dụ: {"state": "on"}
                    
                    # Publish lệnh xuống thiết bị phần cứng
                    actuator_topic = f"smartcampus/rooms/{room_id}/actuators/{tool_name}"
                    await client.publish(actuator_topic, payload=json.dumps(params).encode())
                    
                    # Báo động khẩn cấp lên Dashboard giao diện người dùng
                    await ws_manager.broadcast_to_room(room_id, {
                        "type": "AI_CONTROL_TRIGGERED",
                        "tool": tool_name,
                        "reason": rec["reason"],
                        "urgency": rec.get("urgency", "medium")
                    })
```

---

## 8. Sổ Tay Lệnh Vận Hành & Kiểm Thử

### 1. Khởi động Toàn Bộ Cụm Dịch Vụ
```bash
docker compose up -d
```

### 2. Xem Tiến Trình Tải Model Của Ollama (Nomic + Qwen)
```bash
docker logs -f smartcampus-ollama-init
```

### 3. Kiểm Tra Extension pgvector & Bảng Trong Container
```bash
docker exec -it smartcampus-pgvector psql -U smartcampus -d smartcampus -c "\dn"
docker exec -it smartcampus-pgvector psql -U smartcampus -d smartcampus -c "\dt agent_memory.*"
```

### 4. Kiểm Tra Danh Sách Model Đã Tải Trong Ollama
```bash
curl http://localhost:11434/api/tags
```

### 5. Chạy Thử Nghiệm Kịch Bản Giả Lập Bằng Python
```bash
# Cửa sổ 1: Bật mock backend gateway
python mock_backend.py

# Cửa sổ 2: Chạy demo AI Agent đánh giá 5 kịch bản
python run_agent_demo.py

# Kiểm tra riêng từng RAG tool
python run_rag_tests.py
```
