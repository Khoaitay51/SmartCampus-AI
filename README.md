# 🤖 SmartCampus AI Agent & Central Backend Service

> **Phân hệ Trí tuệ Nhân tạo & Dịch vụ Quản trị Trung tâm (Central Backend & AI Decision Engine)**  
> Xây dựng trên nền tảng **FastAPI**, **AsyncIO**, **PostgreSQL 16 với tiện ích mở rộng pgvector**, **Ollama (Local SLM Qwen2:1.5b & Nomic Embeddings)**, **Google Gemini API**, và **aiomqtt WebSocket Tunnel Bridge**.

---

## 📌 Tổng quan Phân hệ

Thư mục `AI + Backend` đảm nhiệm 3 vai trò trung tâm trong hệ sinh thái SmartCampus BMS:
1. **Central REST API & Authentication:** Cung cấp toàn bộ các API quản trị người dùng, thiết bị, phòng học, phiên học, phân quyền dựa trên vai trò (RBAC) với JWT tokens.
2. **AI ReAct Decision Engine (ReActXenAgent):** Tác nhân thông minh phân tích các sự kiện bất thường từ hệ thống IoT (nhiệt độ tăng, khói, quá tải số người), kết hợp bối cảnh vận hành trượt 15 phút (Operational Context) và tra cứu tri thức (RAG) để đưa ra các đề xuất điều khiển tối ưu.
3. **Kênh Đồng bộ Thời gian thực (Realtime WebSocket Tunnel):** Kết nối trực tiếp với Eclipse Mosquitto MQTT Broker và phát sóng hai chiều tới Giao diện Điều hành 3D Web Frontend với độ trễ dưới 100ms.

---

## 🏛️ Kiến trúc Thành phần (Internal Architecture)

```
                     ┌──────────────────────────────────────────────┐
                     │           Mosquitto MQTT Broker              │
                     └──────────────────────┬───────────────────────┘
                                            │ aiomqtt Pub/Sub
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │    WebSocket & MQTT Bridge (mqtt_bridge.py)   │
                     │  - Lắng nghe smartcampus/v1/...              │
                     │  - Broadcast WebSocket tới /ws/campus        │
                     │  - Trigger AI Agent khi có sự kiện bất thường│
                     └──────┬────────────────────────────────┬──────┘
                            │                                │
          Event Payload     │                                │ Realtime Push (< 100ms)
                            ▼                                ▼
┌──────────────────────────────────────────┐    ┌───────────────────────────────┐
│     Tác nhân AI (ReActXenAgent)          │    │    3D Digital Twin Web UI     │
│  - Chu trình ReAct: Observe→Think→Act    │    │  - Popup cảnh báo & đề xuất   │
│  - Dynamic Few-Shot từ pgvector LTM      │    │  - Modal duyệt [Execute/Ignore│
│  - LLM: Qwen2:1.5b (Ollama) / Gemini     │    └───────────────────────────────┘
│  - Quản lý ngân sách gọi RAG (max 4 calls│
└───────────────────┬──────────────────────┘
                    │ Tool Recommendations
                    ▼
┌──────────────────────────────────────────┐    ┌───────────────────────────────┐
│     Human-in-the-Loop & Autopilot        │    │    PostgreSQL 16 + pgvector   │
│  - HITL: Đợi Admin phê duyệt trên Web UI │◄───┤  - agent_memory.contextual... │
│  - Autopilot: Tự thực thi khi Conf ≥ 0.8 │    │  - agent_memory.campus_docs   │
│  - Cooldown 60s & An toàn cửa/FSM        │    │  - agent_memory.experience_logs│
└──────────────────────────────────────────┘    └───────────────────────────────┘
```

---

## 🛠️ Các Tính năng Kỹ thuật Chính

### 1. Chu trình Suy luận ReAct (Observe $\rightarrow$ Think $\rightarrow$ Act)
* **Observe (Quan sát):** Nhận sự kiện bất thường kèm theo bản chụp bối cảnh vận hành 15 phút (Min/Max/Avg nhiệt độ, độ ẩm, nồng độ khí CO2, số người hiện diện, trạng thái cửa/quạt).
* **Think (Suy nghĩ):** Mô hình ngôn ngữ phân tích nguyên nhân sự cố dựa trên quy chuẩn vận hành chuẩn (SOP) và các kinh nghiệm quá khứ đã được con người duyệt (Dynamic Few-Shot).
* **Act (Hành động):** Tác nhân lựa chọn công cụ từ danh mục công cụ an toàn:
  * `set_fan`: Bật/tắt quạt thông gió.
  * `set_door`: Đóng/mở chốt cửa servo.
  * `set_mode`: Chuyển đổi trạng thái máy FSM phòng học.
  * `trigger_buzzer`: Kích hoạt còi báo động khẩn cấp.
  * `send_alert`: Đẩy thông báo cảnh báo mức cao lên giao diện web.
  * `set_led`: Đổi màu dải đèn chỉ thị trạng thái.

### 2. Bộ nhớ Dài hạn & RAG trên pgvector
* **Contextual Memory Logs (`agent_memory.contextual_memory_logs`):** Lưu trữ tóm tắt vi khí hậu theo từng phòng học kèm vector nhúng 768 chiều (tạo bởi mô hình `nomic-embed-text`).
* **Campus SOP Documents (`agent_memory.campus_documents`):** Lưu trữ các quy trình vận hành tiêu chuẩn của trường (ngưỡng nhiệt độ an toàn, quy định phòng thi, phương án xử lý cháy nổ).
* **Experience Log (`agent_memory.agent_experience_logs`):** Lưu lại các quyết định đã được con người bấm duyệt (`human_approved = true`). Khi gặp tình huống mới tương tự, hệ thống tự động tìm kiếm cosine distance để đưa vào prompt làm mẫu (Dynamic Few-Shot learning).

### 3. Cơ chế Phê duyệt Quyết định (HITL & Autopilot)
* **HITL Mode (Human-in-the-Loop):** Mặc định bật. Mọi đề xuất công cụ từ AI Agent được gửi về bảng `ai_recommendations` với trạng thái `PENDING`. Người quản trị nhìn thấy popup thời gian thực và bấm duyệt `[Thực thi]` hoặc `[Bỏ qua]`.
* **Autopilot Mode:** Khi kích hoạt, hệ thống tự động thực thi các đề xuất có độ tin cậy $\ge 0.8$ nhằm giảm tải cho người trực ca. Tuy nhiên:
  * Cooldown an toàn 60 giây giữa các lệnh trên cùng 1 phòng.
  * Các lệnh liên quan đến an ninh (khóa/mở cửa, chuyển đổi trạng thái FSM) luôn bắt buộc phải có sự xác nhận của con người.

### 4. Hệ thống Quản trị & Xác thực Người dùng
* **JWT Authentication:** Cấp phát Access Token chuẩn OAuth2 Password Bearer.
* **Phân quyền 3 cấp (RBAC):**
  * `ADMIN`: Toàn quyền quản trị, chuyển đổi mọi chế độ phòng, duyệt thẻ lạ, duyệt hành động AI, bật/tắt Autopilot.
  * `LECTURER`: Giảng viên quản lý phiên học, xem điểm danh lớp học, điều khiển quạt/cửa phòng dạy.
  * `STUDENT`: Sinh viên xem thông tin phòng học, không có quyền can thiệp vào máy trạng thái hoặc thiết bị.
* **Audit Logging:** Lưu vết toàn bộ các hành động thực thi, thời gian, IP và tài khoản thao tác vào bảng `audit_logs`, hỗ trợ xuất báo cáo định dạng CSV.

---

## 📂 Cấu trúc Thư mục Mã nguồn

```
AI + Backend/
├── app/
│   ├── main.py                     # Entrypoint ứng dụng FastAPI & Lifespan setup
│   ├── agent/                      # Logic Tác nhân AI ReAct
│   │   ├── agent.py                # ReActXenAgent & Dynamic Few-Shot logic
│   │   ├── loop.py                 # Vòng lặp suy luận ReAct (ReActLoopRunner)
│   │   ├── prompts.py              # System prompt, chính sách công cụ và few-shot
│   │   ├── output_parser.py        # Parser bóc tách kết quả JSON từ LLM
│   │   └── state.py                # Trạng thái theo dõi bước suy luận
│   ├── api/                        # Danh mục các Router REST API
│   │   ├── auth.py                 # Đăng nhập OAuth2, lấy thông tin cá nhân
│   │   ├── campus_rooms.py         # Quản lý danh mục & FSM mode của phòng học
│   │   ├── campus_devices.py       # Quản lý danh sách thiết bị ESP32
│   │   ├── campus_users.py         # Quản lý tài khoản và phân quyền người dùng
│   │   ├── campus_recommendations.py # Quản lý khuyến nghị AI & Phê duyệt HITL
│   │   ├── campus_chat.py          # Trợ lý hội thoại hỏi đáp RAG
│   │   ├── campus_audit.py         # Xem và xuất báo cáo nhật ký kiểm toán CSV
│   │   ├── campus_telemetry.py     # Tra cứu chuỗi thời gian nhiệt độ, CO2, số người
│   │   └── campus_events.py        # Tra cứu các sự kiện bất thường gần nhất
│   ├── campus/                     # Logic quản lý trạng thái nghiệp vụ
│   │   └── hitl.py                 # Bộ quản lý trạng thái HITL & Autopilot
│   ├── config/                     # Cấu hình Pydantic Settings từ .env
│   ├── database/                   # Kết nối SQLAlchemy Async Session & Models
│   │   ├── models.py               # ORM Models (User, AIRecommendation, AuditLog...)
│   │   └── session.py              # Async engine kết nối PostgreSQL/pgvector
│   ├── gateway/                    # Tương tác với Edge Gateway & pgvector
│   │   ├── client.py               # HTTP client gọi sang Edge API (cổng 8000)
│   │   ├── embeddings.py           # Sinh vector nhúng (Ollama / Voyage)
│   │   └── rag.py                  # Công cụ tra cứu vector memory & SOP
│   ├── llm/                        # Abstraction client cho các nhà cung cấp LLM
│   │   ├── client.py               # Base LLM client
│   │   ├── gemini.py               # Tích hợp Google Gemini API
│   │   └── ollama.py               # Tích hợp Ollama Local SLM (Qwen2:1.5b)
│   ├── tools/                      # Định nghĩa danh mục công cụ
│   │   └── registry.py             # Action tools & RAG query tools
│   └── websocket/                  # Quản lý kênh truyền thời gian thực
│       └── mqtt_bridge.py          # aiomqtt bridge lắng nghe MQTT & phát WebSocket
├── Dockerfile                      # Docker container build cho AI Service
├── docker-compose.yml              # Dựng pgvector, ollama, ollama-init, ai-agent
├── requirements.txt                # Danh mục thư viện Python
└── .env.example                    # File cấu hình môi trường mẫu
```

---

## ⚙️ Cấu hình Biến Môi trường (`.env`)

Tạo file `.env` từ file mẫu `.env.example`:

```ini
# LLM Provider: 'ollama' hoặc 'gemini'
LLM_PROVIDER=ollama
AGENT=gemini-1.5-flash
GEMINI_API_KEY=your_gemini_api_key_here

# Ollama Local Service
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2:1.5b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# PostgreSQL + pgvector
POSTGRES_DB=smartcampus
POSTGRES_USER=smartcampus
POSTGRES_PASSWORD=change-this-local-password
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://smartcampus:change-this-local-password@db:5432/smartcampus

# Embedding Configuration
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768

# Edge Gateway URL
BACKEND_BASE_URL=http://host.docker.internal:8000

# JWT Authentication
SECRET_KEY=smartcampus-super-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# MQTT Broker (aiomqtt bridge)
MQTT_BROKER_HOST=mosquitto
MQTT_BROKER_PORT=1883
MQTT_USERNAME=smartcampus
MQTT_PASSWORD=change-this-mqtt-password
MQTT_CLIENT_ID=smartcampus-ai-bridge
```

---

## 🚀 Hướng dẫn Chạy Dịch vụ

### Chạy qua Docker Compose (Khuyến nghị)
Phân hệ được tích hợp sẵn trong file `docker-compose.yml` tổng ở thư mục gốc hoặc có thể chạy độc lập:

```bash
docker compose up -d --build
```

Kiểm tra trạng thái các container:
* `smartcampus-ai`: Chạy FastAPI server tại cổng `8001` (ánh xạ từ container cổng `8000`).
* `smartcampus-pgvector`: Chạy PostgreSQL 16 tại cổng `5433`.
* `smartcampus-ollama`: Chạy Ollama server tại cổng `11436`.

### Kiểm tra API & Tài liệu Swagger
* **Tài liệu Swagger UI:** [http://localhost:8001/docs](http://localhost:8001/docs)
* **Kiểm tra Healthcheck:**
  ```bash
  curl http://localhost:8001/api/health
  ```
  Phản hồi: `{"status":"ok","timestamp":"...","database":"connected","mqtt_bridge":"connected"}`

---
*Smart Campus BMS — Phân hệ AI Agent & Central Backend.*