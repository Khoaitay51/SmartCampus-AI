# SmartCampus AI Agent

Thư mục này chứa mã nguồn của AI Agent sử dụng trong hệ thống SmartCampus. Agent (được xây dựng dựa trên kiến trúc `ReActXenAgent`) có khả năng: 
- Nhận các sự kiện từ hệ thống IoT (ví dụ: nhiệt độ, chất lượng không khí, trạng thái phòng).
- Phân tích ngữ cảnh (Operational Context).
- Gọi các công cụ RAG (để lấy dữ liệu lịch sử/dự báo từ Edge Gateway).
- Đưa ra các hành động điều khiển thiết bị (Control Actions) để tự động hóa giảm tải, tiết kiệm năng lượng hoặc phát ra cảnh báo.

## Cấu trúc thư mục

- `app/`: Chứa mã nguồn chính của hệ thống Agent (bao gồm models/schemas, logic agent, gateway client,...).
- `mock_backend.py`: Script chạy Mock Server (bằng FastAPI) giúp giả lập môi trường Edge Gateway & RAG API (chạy ở cổng 8000). 
- `run_agent_demo.py`: Script dùng để khởi chạy demo Agent với các kịch bản mẫu đã được thiết lập.
- `run_rag_tests.py`: Script dùng để chạy các kịch bản test riêng biệt cho công cụ RAG (để kiểm tra xem LLM có hiểu và trích xuất đúng parameters hay không).
- `AI_AGENT_SCENARIO_GUIDE.md`: Hướng dẫn chi tiết các kịch bản để training/chạy Agent.
- `requirements.txt`: Danh sách các thư viện Python cần thiết (như `fastapi`, `google-genai`, `pydantic`,...).

## Cài đặt (Installation)

1. **Yêu cầu hệ thống**: Python 3.9 trở lên.
2. **Tạo môi trường ảo (Virtual Environment) và cài đặt**:

```bash
# Tạo môi trường ảo
python -m venv venv

# Kích hoạt venv (Windows)
venv\Scripts\activate
# Kích hoạt venv (Linux/MacOS)
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

3. **Cấu hình môi trường**:
Hãy đảm bảo bạn đã tạo và cấu hình file `.env` tại thư mục này với nội dung tương tự sau:

```env
# Cấu hình API key cho AI (Gemini hoặc model khác tuỳ thuộc config)
GEMINI_API_KEY=your_google_api_key_here

# Trỏ gateway về local để test với mock_backend
GATEWAY_URL=http://localhost:8000/api
```

## Hướng dẫn chạy Mock Backend

Mock Backend vô cùng hữu ích khi bạn muốn test Agent gọi HTTP request thực sự sang Gateway mà không cần dựng PostgreSQL hay kết nối với mạng cảm biến IoT thật.

Mở một terminal mới (nhớ active venv) và chạy:
```bash
python mock_backend.py
```
> Server sẽ start tại `http://127.0.0.1:8000`. Mock backend giả lập cả các endpoint lấy dự báo nhiệt độ, và trả về context giả của các phòng.

## Hướng dẫn chạy Agent Demo

Sau khi Mock Backend đã chạy, mở một cửa sổ terminal thứ 2 và chạy:

```bash
python run_agent_demo.py
```
hoặc
```bash
python run_rag_tests.py
```
**Các tuỳ chọn của Agent demo:**
- `python run_agent_demo.py`: Chạy toàn bộ 5 kịch bản được code sẵn trong mảng `TRAINING_SCENARIOS`.
- `python run_agent_demo.py --list-rooms`: Hiển thị danh sách các phòng được lấy từ mock backend.
- `python run_agent_demo.py --room <room_id>`: Gọi mock backend để lấy context của `room_id` cụ thể và cho Agent xử lý.

## Testcases & Kịch bản

Bạn có thể chạy các bài test của chức năng RAG riêng lẻ bằng lệnh:
```bash
python run_rag_tests.py
```

### Một số kịch bản điển hình (Testcases) mà Agent có thể xử lý:
1. **Cảnh báo nhiệt độ tăng (room-temp-trend-check):**
   - **Trigger:** Nhận event nhiệt độ bắt đầu cao.
   - **Action:** Agent gọi RAG dự báo (predict 15m), phát hiện sắp vượt ngưỡng an toàn (34°C). Quyết định bật AC, đặt nhiệt độ 22°C và gửi cảnh báo `OVERHEAT_WARNING`.
2. **CO2/AQI vượt mức:**
   - **Trigger:** Chất lượng không khí (CO2) tăng vọt.
   - **Action:** Agent phân tích, quyết định bật quạt thông gió (Ventilation) và kích hoạt đèn/chế độ cảnh báo.
3. **Tiết kiệm năng lượng (Energy Waste):**
   - **Trigger:** Đèn hoặc AC đang bật nhưng phòng không có người (occupancy = 0).
   - **Action:** Agent tự động điều chỉnh tắt các thiết bị điện thừa thãi.
4. **Bảo mật (Cửa mở quá lâu):**
   - **Trigger:** Door sensor báo MỞ nhưng phòng lại trống hoặc hệ thống AC đang chạy.
   - **Action:** Gửi Alert đóng cửa.

> **Chi tiết thiết kế testcase và flow xử lý:** Tham khảo thêm file `AI_AGENT_SCENARIO_GUIDE.md`.
