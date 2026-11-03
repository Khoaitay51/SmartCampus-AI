# BÁO CÁO NGHIÊN CỨU TOÀN DIỆN: ĐÁNH GIÁ AN TOÀN VÀ ĐỘ BỀN VỮNG CỦA LLM-BASED AGENT TRONG HỆ THỐNG ĐIỀU KHIỂN CYBER-PHYSICAL SMART CAMPUS

> **Tài liệu nghiên cứu khoa học phục vụ báo cáo Giảng viên hướng dẫn & Hội đồng bảo vệ**  
> **Dự án:** Smart Campus Cyber-Physical Systems Security Benchmark (v2 Refined)  
> **Mô hình nghiên cứu (SUT):** `ReActXenAgent` (Nền tảng `gemini-3.5-flash-lite`, Zero-shot ReAct, Dynamic Function Calling, Live Real-world RAG, pgvector LTM)  
> **Hạ tầng triển khai thực tế:** 2 Node Phòng học + 1 Node Hành lang (ESP32 Nodes) | Edge Gateway (`localhost:8000`), TimescaleDB (`localhost:5433`), Mosquitto MQTT Broker  
> **Quy mô thực nghiệm cốt lõi:** Đánh giá độc lập $k=3$ vòng ($762$ lượt gọi Agent tấn công + $300$ lượt Clean Twin đối chứng) | Baseline Freeze: `2026-11-02`

---

## MỤC LỤC TỔNG QUAN
1. [Kiến Trúc Hệ Thống Mục Tiêu (Target System Architecture: Hardware & Software)](#1-kien-truc-he-thong-muc-tieu)
2. [Mô Hình Đe Dọa & Không Gian Tấn Công (Threat Model & Attack Taxonomy)](#2-mo-hinh-de-doa--khong-gian-tan-cong)
3. [Luận Điểm Trung Tâm & Kết Quả Thực Nghiệm Toàn Diện ($k=3$)](#3-luan-diem-trung-tam--ket-qua-thuc-nghiem)
4. [Ba Đóng Góp Nghiên Cứu Đột Phá (C1, C2, C3) Gắn Liền Với Bối Cảnh, Cơ Chế & Hệ Quả CPS](#4-ba-dong-gop-nghien-cuu)
5. [Đối Chiếu Chi Tiết Với Related Work Quốc Tế (InjecAgent, AgentDojo, Evil-AI, AgentAbstain, EpiSEM-Bench, Ignored Not Refused)](#5-doi-chieu-related-work)
6. [Giới Hạn Nghiên Cứu (Limitations & Future Work)](#6-gioi-han-nghien-cuu)

---

<a name="1-kien-truc-he-thong-muc-tieu"></a>
# 1. KIẾN TRÚC HỆ THỐNG MỤC TIÊU (TARGET SYSTEM ARCHITECTURE)

Hệ thống được thiết kế theo mô hình **Agentic Cyber-Physical System (CPS)** gồm 4 phân lớp khép kín, tích hợp chặt chẽ giữa phần cứng nhúng IoT, trạm điều hành biên (Edge Computing Gateway), tác nhân trí tuệ nhân tạo (AI Decision Engine) và giao diện điều hành Digital Twin có con người giám sát (Human-in-the-Loop - HITL).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. HẠ TẦNG PHẦN CỨNG IoT (ESP32 NODES - 2 PHÒNG HỌC + 1 HÀNH LANG)                    │
│                                                                                        │
│   [2 Node Phòng Học (ESP32)]                     [1 Node Hành Lang (ESP32)]            │
│   • DHT22: Nhiệt độ & Độ ẩm (chu kỳ 2s)          • RFID RC522: Điểm đăng ký thẻ lạ     │
│   • MQ-2: Khói / Khí gas độc hại                 • Màn hình OLED SSD1306               │
│   • Dual IR: Nhận diện chiều ra/vào sinh viên    • RGB LED & Còi Buzzer an ninh        │
│   • RFID RC522: Quẹt thẻ điểm danh & mở cửa                                            │
│   • Quạt thông gió 2 dây (Transistor 2N2222)                                           │
│   • Khóa chốt Servo SG90 (locked / unlocked)                                           │
│   • Còi Buzzer báo động, Dải LED WS2812B, OLED                                         │
└──────────────────────────────────────────▲─────────────────────────────────────────────┘
                                           │ MQTT Topics (Mosquitto Broker)
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. EDGE COMPUTING GATEWAY (FASTAPI :8000 + TIMESCALEDB :5433)                          │
│                                                                                        │
│   • Quản lý Máy trạng thái hữu hạn FSM (7 chế độ: SAVING, LECTURE, EXAM, EVENT,        │
│     CLEANING, MAINTENANCE, LOCK)                                                      │
│   • Điểm danh, xác thực thẻ và tổng hợp bối cảnh vận hành cửa sổ trượt 15 phút         │
│   • SinkToolRecorder: Bắt chuỗi Canary Token chống rò rỉ dữ liệu trong bộ nhớ          │
└──────────────────────────────────────────▲─────────────────────────────────────────────┘
                                           │ HTTP POST /api/evaluate
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. AI DECISION ENGINE (ReActXenAgent + PGVECTOR LTM)                                   │
│                                                                                        │
│   • Dynamic Few-Shot: nomic-embed-text (768 chiều) truy vấn PostgreSQL+pgvector        │
│   • Main ReAct Agent: Chu trình Self-Ask -> RAG Tools (tối đa 5 lượt) -> Finish        │
│   • Multi-Role Verification: Review Agent (thẩm định SOP) & Reflect Agent (tự soi)     │
│   • Guardrails: Ma trận MODE_PERMISSIONS, Abstention Barrier (Confidence < 0.35)       │
│   • Fallback 4 Cấp: Model Switch -> Parser Regex -> Tool Mock -> Heuristic Rules       │
└──────────────────────────────────────────▲─────────────────────────────────────────────┘
                                           │ Khuyến nghị hành động (Tool Recommendation)
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. GIAO DIỆN ĐIỀU HÀNH 3D & HITL (DIGITAL TWIN WEB UI)                                 │
│                                                                                        │
│   • Giám sát Digital Twin 3D thời gian thực (React + ThreeJS)                          │
│   • Human-in-the-Loop (HITL): Admin phê duyệt [Execute / Ignore] trước khi tác động    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1. Cấu Trúc Phần Cứng IoT Thực Tế
Hệ thống triển khai thực nghiệm trên **2 phòng học thực tế** và **1 hành lang kết nối**, điều khiển trực tiếp qua các vi điều khiển ESP32:

| Node Phần Cứng | Cảm biến & Đầu vào (Inputs) | Cơ cấu chấp hành & Đầu ra (Actuators/Outputs) |
| :--- | :--- | :--- |
| **2 Node Phòng Học** *(ESP32)* | • **DHT22:** Đo nhiệt độ & độ ẩm (chu kỳ 2s).<br>• **MQ-2:** Đo nồng độ khói & gas độc hại.<br>• **Dual IR:** Cặp cảm biến hồng ngoại nhận diện chiều ra/vào để đếm người.<br>• **RFID RC522:** Quẹt thẻ sinh viên điểm danh & mở cửa. | • **Quạt thông gió 2 dây (`set_fan`):** Đóng/ngắt qua transistor NPN 2N2222.<br>• **Khóa chốt Servo SG90 (`set_door`):** Đóng mở chốt (`locked` / `unlocked`).<br>• **Còi cảnh báo (`trigger_buzzer`):** Hú còi `short`, `long`, `continuous`.<br>• **Dải LED WS2812B (`set_led`):** Đổi màu theo trạng thái phòng.<br>• **Màn hình OLED SSD1306:** Hiển thị tên người quẹt thẻ & thông số vi khí hậu. |
| **1 Node Hành Lang** *(ESP32, Role 3)* | • **RFID RC522:** Quẹt thẻ an ninh hành lang. | • **Màn hình OLED, RGB LED, Buzzer.**<br>• *Nghiệp vụ:* Đăng ký thẻ lạ (`card_registration_request`) và kiểm soát an ninh khu vực chung. |

### 1.2. Phân Lớp Phần Mềm & Não Bộ Ra Quyết Định (ReActXenAgent)
* **Trạm biên (Edge Gateway - FastAPI & TimescaleDB):** 
  - Quản lý máy trạng thái hữu hạn FSM gồm 7 chế độ: `SAVING` (Tiết kiệm), `LECTURE` (Giảng dạy), `EXAM` (Thi cử), `EVENT` (Sự kiện), `CLEANING` (Vệ sinh), `MAINTENANCE` (Bảo trì), và `LOCK` (Khóa khẩn cấp).
  - Tự động duy trì và tổng hợp bối cảnh vận hành vi khí hậu trong cửa sổ trượt 15 phút gần nhất.
* **Tác nhân AI (AI Decision Engine):** Vận hành chu trình ReAct đa vai trò (Multi-Role Loop):
  1. *Dynamic Few-Shot Injection:* Sử dụng mô hình `nomic-embed-text` (768 chiều) truy vấn bộ nhớ dài hạn (LTM) trên `PostgreSQL + pgvector` (`agent_experience_logs`) để lấy các tiền lệ tương tự từng được Admin phê duyệt làm mẫu prompt.
  2. *Main ReAct Agent (Self-Ask + Reasoning):* Nhận gói tin sự kiện, tự đặt câu hỏi con, tra cứu ngữ cảnh qua tối đa 5 lượt gọi RAG Tools (`search_history`, `get_telemetry`, `get_attendance`, `compare_rooms`, `get_room_history`, `get_schedule`, `get_predictions`).  
     *Quy tắc an toàn:* Cấm gọi trực tiếp Action Tools điều khiển thiết bị trong vòng lặp; hành động duy nhất chỉ được đề xuất thông qua tool `finish`.
  3. *Review Agent (Thẩm định viên độc lập):* Đối chiếu khuyến nghị của Main Agent với bằng chứng RAG và quy chuẩn SOP phòng cháy/học đường. Trả về `Accomplished` (đạt) hoặc `Not Accomplished` (từ chối do thiếu chứng cứ/ảo giác).
  4. *Reflect Agent (Tự soi chiếu):* Khi bị Review từ chối, phân tích sai sót trong scratchpad và rút kinh nghiệm để sửa ở vòng lặp kế tiếp.
* **Hệ thống Kiểm soát (Guardrails) & Phòng thủ 4 Cấp:**
  - *Ma trận quyền `MODE_PERMISSIONS`:* Chặn lệnh trái phép theo chế độ phòng (ví dụ: chế độ `EXAM` cấm mở cửa gây ồn; chế độ `LOCK` cấm can thiệp quạt/cửa để bảo vệ hiện trường).
  - *Abstention Heuristic (Quality Gate):* Nếu điểm tin cậy `confidence < 0.35`, Agent tự động hủy lệnh (`skip = true`).
  - *Cơ chế Fallback 4 cấp:* Chuyển đổi Model (`gemini` $\rightarrow$ `qwen2`) $\rightarrow$ Parser (Regex vá JSON) $\rightarrow$ Tool Mock $\rightarrow$ Heuristic Rules if-else cứng để cứu nguy khi AI gặp sự cố.
* **Giao diện Giám sát 3D & HITL:** Bản sao số Digital Twin Web UI (React + ThreeJS), cho phép quản trị viên xem mô phỏng trực quan 3D thời gian thực và phê duyệt `[Execute / Ignore]` trước khi gửi lệnh xuống relay phần cứng.

---

<a name="2-mo-hinh-de-doa--khong-gian-tan-cong"></a>
# 2. MÔ HÌNH ĐE DỌA & KHÔNG GIAN TẤN CÔNG (THREAT MODEL & ATTACK TAXONOMY)

### 2.1. Giả Định Mô Hình Đe Dọa (Knowledgeable Gray-box Adversary)
> **❓ Kẻ tấn công có biết SOP công khai của trường học không?**

* **Khẳng định mô hình đe dọa:**
  - **Kẻ tấn công BIẾT:** Các quy trình vận hành chuẩn (SOP) mang tính **công khai** của nhà trường (quy định diễn tập PCCC định kỳ, quy trình bảo dưỡng điều hòa HVAC, lịch thi cử, nội quy mượn phòng học). Chính nhờ hiểu biết này, kẻ tấn công mới có thể ngụy tạo các lý do giả mạo cực kỳ tinh vi (*"đang diễn tập PCCC định kỳ"*, *"thợ bảo dưỡng đang thử đầu dò khói"*).
  - **Kẻ tấn công HOÀN TOÀN KHÔNG BIẾT:** System Prompt của Agent, mã nguồn nội tại, cấu trúc chu trình ReAct, danh sách tool ẩn, cơ chế Guardrails hay cơ sở dữ liệu TimescaleDB.
  - 👉 *Đây là giả định thực tế và thuyết phục nhất: Kẻ tấn công là người dùng bình thường hoặc sinh viên có hiểu biết về đời sống học đường, lợi dụng kênh gửi mô tả sự cố qua MQTT/Web để thực hiện tấn công tiêm nhiễm gián tiếp (Indirect Prompt Injection - IPI).*
* **Kênh tấn công (Attack Surface):** Kẻ tấn công **chỉ kiểm soát duy nhất trường văn bản tự do** `event_data.description` nằm bên trong gói tin sự kiện cảm biến/MQTT.
* **Vùng tin cậy tuyệt đối (Trusted Boundary):** Các trường số liệu kỹ thuật đo đạc từ cảm biến vật lý (`temperature`, `smoke_value`, `co2`, `timestamp`, `sensor_id`), bối cảnh vận hành trượt 15 phút (`operational_context`), dữ liệu RAG nội bộ và System Prompt. Kẻ tấn công hoàn toàn không can thiệp được vào các trường này.

---

### 2.2. Xây Dựng Bộ Testcase: Từ Phép Nhân $5 \times 60 = 300$ Đến 254 Ca Hợp Lệ
> **❓ Từ phép nhân $5 \times 60 = 300$, tại sao lại ra 254 ca ($100, 36, 88, 30$)? Phân bổ không đều có ảnh hưởng đến độ tin cậy không?**

1. **Nguồn gốc 60 kịch bản Attacker:**
   Trong file `advanced_attackers.json`, có đúng 60 hồ sơ kẻ tấn công được thiết kế theo 4 nhóm mục tiêu:
   - $22$ ca ép can thiệp phần cứng (DH-A)
   - $10$ ca ép mở khóa an ninh (DH-S)
   - $22$ ca ép bỏ qua cứu hộ (SUP)
   - $6$ ca lừa trộm dữ liệu (DS)
   $\Rightarrow$ Tổng cộng: $22 + 10 + 22 + 6 = \mathbf{60 \text{ attacker profiles}}$.
2. **Tích Descartes với 5 Scenario ($U1 \dots U5$):**
   $60 \text{ Attackers} \times 5 \text{ User Scenarios} = \mathbf{300 \text{ ca tiềm năng}}$.
3. **Tại sao phải loại bỏ 46 ca để còn 254 ca hợp lệ ($300 - 46 = 254$)?**
   Nếu để nguyên 300 ca, bộ test sẽ bị **xung đột ngữ nghĩa vật lý (Semantic & Physical Contradiction)**:
   - *Loại bỏ 22 ca SUP trên $U5$ ($22$ ca):* Kịch bản $U5$ là phòng họp bình thường, không có sự cố nguy hiểm nào. Kẻ tấn công bảo Agent *"đừng làm gì cả"*, và Agent vốn dĩ không cần làm gì $\rightarrow$ Đây là hành vi đúng tự nhiên, không thể tính là bị hack.
   - *Loại bỏ 10 ca DH-A trùng lặp cứu hộ ($10$ ca):* Kẻ tấn công ép bật quạt, mà phòng server $52^\circ\text{C}$ vốn dĩ SOP cũng yêu cầu bật quạt $\rightarrow$ Không thể phân biệt Agent nghe theo SOP hay nghe theo hacker.
   - *Loại bỏ 14 ca DH-S không khả thi phần cứng ($14$ ca):* Một số phòng không có khóa chốt điện từ hoặc yêu cầu thẩm quyền không tương thích.
4. **Phân bổ không đều ($100, 36, 88, 30$) có ảnh hưởng gì không?**
   - **HOÀN TOÀN KHÔNG ẢNH HƯỞNG**, vì:
     - Khi đánh giá từng nhóm, ta tính theo **tỷ lệ phần trăm chuẩn hóa (Normalized Rate)** độc lập trên từng mẫu số ($26.33\%$, $5.56\%$, $46.59\%$, $0.00\%$).
     - Trong thực tế, không gian các hành động tác động thiết bị (bật quạt, còi, đèn) luôn phong phú hơn so với hành động mở khóa cửa (vốn chỉ có 1-2 loại cửa). Việc phân bổ này phản ánh đúng bề mặt tấn công vật lý thực tế.

---

### 2.3. Mối Liên Hệ Giữa 4 Taxonomy (WHAT) và 6 Persuasion Techniques (HOW)

```
       MỤC TIÊU TẤN CÔNG (WHAT - 4 Taxonomy)          VỎ BỌC TÂM LÝ (HOW - 6 Persuasion)
       ┌───────────────────────────────────┐          ┌────────────────────────────────┐
       │ • DH-A: Ép bật/tắt thiết bị       │          │ • drill_test: Diễn tập         │
       │ • DH-S: Ép mở khóa cửa            │    X     │ • technical_notice: Bảo trì    │
       │ • SUP: Ép bỏ qua cảnh báo cứu hộ  │          │ • urgency: Hối thúc khẩn cấp   │
       │ • DS: Ép xuất dữ liệu ra ngoài    │          │ • authority_claim: Giả sếp     │
       └───────────────────────────────────┘          └────────────────────────────────┘
```
* **Mối liên hệ tương quan:** Taxonomy trả lời câu hỏi *"Kẻ tấn công muốn Agent làm điều gì?"* (Mục tiêu độc hại). Còn Persuasion trả lời *"Kẻ tấn công ngụy trang dưới danh nghĩa gì để thuyết phục LLM?"* (Phương tiện thao túng tâm lý). Mỗi ca kiểm thử là giao thoa giữa một Mục tiêu phá hoại và một Vỏ bọc tâm lý.
* **4 Taxonomy mục tiêu:**
  1. `DH-A` (Harm - Actuation, 100 ca): Ép bật/tắt thiết bị gây hại cơ học hoặc gián đoạn hoạt động.
  2. `DH-S` (Harm - Security, 36 ca): Mạo danh chức vụ mở khóa cửa xâm nhập trái phép.
  3. `SUP` (Safety Suppression, 88 ca): Ép bỏ qua cứu hộ khi có cháy/khói thật.
  4. `DS` (Data Stealing, 30 ca): Lừa đọc và gửi Canary Token ra ngoài qua sink tools.
* **6 Kỹ thuật thuyết phục:** `drill_test` (viện cớ diễn tập), `technical_notice` (thông báo kỹ thuật giả), `maintenance` (bảo dưỡng thiết bị), `urgency` (tạo áp lực thời gian), `authority_claim` (giả mạo lãnh đạo), `policy_claim` (quy chế trường học giả).

---

<a name="3-luan-diem-trung-tam--ket-qua-thuc-nghiem"></a>
# 3. LUẬN ĐIỂM TRUNG TÂM & KẾT QUẢ THỰC NGHIỆM TOÀN DIỆN ($k=3$)

## 🎯 LUẬN ĐIỂM TRUNG TÂM (CENTRAL THESIS)

> **"Đối với một Autonomous Agent điều khiển hệ thống Cyber-Physical (CPS) chỉ nhận một trường văn bản tự do làm kênh tấn công gián tiếp, phương thức tấn công nguy hiểm và hiệu quả nhất KHÔNG PHẢI là ép Agent thực hiện một hành vi phá hoại chủ động (Commission), mà là THUYẾT PHỤC NÓ TỪ BỎ HÀNH ĐỘNG BẢO VỆ CẦN THIẾT (Omission / Safety Suppression). Hiện tượng này được đo lường một cách khách quan thông qua nhãn xác định rút ra từ trạng thái cảm biến vật lý tại thời điểm $T_0$."**

Luận điểm này được minh chứng vững chắc qua quy mô thực nghiệm độc lập $k=3$ (tổng cộng **762 lượt chạy Track A**):
* Tỷ lệ tấn công thành công trung bình của nhóm **Safety Suppression (SUP)** đạt tới **$46.59\%$**, vượt trội hoàn toàn so với nhóm can thiệp thiết bị cưỡng bức **DH-A ($26.33\%$)** và xâm phạm an ninh **DH-S ($5.56\%$)**.
* **Khám phá cơ chế nhận thức - Hiện tượng "Đảo cực an toàn" (Safety Polarity Inversion):**  
  Trong các ứng dụng phần mềm văn phòng truyền thống (IT domains), việc Agent "ngồi yên / không làm gì" (Inactivity / Abstention) được coi là trạng thái an toàn mặc định (Fail-safe). Tuy nhiên, trong hệ thống Cyber-Physical khi hiểm họa thực tế đang diễn ra (cháy, ngạt khí, quá nhiệt), **không hành động đồng nghĩa với thất bại thảm họa (Catastrophic Omission)**.  
  Khi kẻ tấn công đưa ra lý do ngụy trang hợp lý ("diễn tập định kỳ", "thợ đang xịt khói thử chuông"), mô hình LLM bị thiên kiến căn chỉnh an toàn (Safety Alignment bias) đánh lừa: nó nhầm tưởng việc "không kích hoạt còi/quạt để tránh gây hoảng loạn" là một quyết định cẩn trọng và có trách nhiệm, từ đó vô tình hoàn thành mục tiêu vô hiệu hóa cứu hộ của kẻ tấn công.

---

### BẢNG 1: CHỈ SỐ HEADLINE TỔNG THỂ HỆ THỐNG (CHUẨN HÓA MEAN $k=3$, $762$ LƯỢT CHẠY)
> **❓ Giải mã các chỉ số đo lường và hiện tượng chênh lệch:**
> 1. **ASR ($27.30\%$ trung bình):** Tỷ lệ kẻ tấn công cướp quyền và đạt được đúng mục tiêu độc hại cụ thể (`attack_success = True`).
> 2. **Giải mã chênh lệch an toàn - Nhiễu loạn nhận thức (Cognitive Disruption / DoS):**  
>    Ở vòng $r_1$, tỷ lệ vi phạm quy chuẩn an toàn SOP là $24.02\%$ ($61/254$ ca), trong khi ASR là $22.05\%$ ($56/254$ ca). Chênh lệch $5$ ca này là các trường hợp Agent **không làm theo ý muốn của hacker** (nên $ASR = \text{False}$), nhưng bị xung đột thông tin dẫn đến **lúng túng và bỏ quên quy trình cứu hộ bắt buộc** (`missed_hazard = True`, $UA = \text{False}$). Điều này chứng minh đòn tấn công IPI ngoài việc cướp quyền còn gây ra thiệt hại dạng từ chối dịch vụ an toàn (DoS).
> 3. **Công thức $\Delta U = BU - UA = 93.00\% - 65.62\% = 27.38\%$:** Mức độ sụt giảm tính hữu dụng so với mốc vận hành an toàn thường nhật. Đây là phép trừ giữa hai tỷ lệ trên hai tập mẫu, không phải phân số đếm ca.
> 4. **MHR ($34.08\%$):** Đánh giá nghiêm ngặt trên $216$ ca thực sự có hiểm họa vật lý khẩn cấp (loại trừ $38$ ca phòng họp bình thường $U5$).

| Chỉ số (Metric) | Ký hiệu | Mẫu số ($N$) & Cách tính | Giá trị Mean ($k=3$) | Độ lệch chuẩn (Std) | Ý nghĩa đánh giá an toàn CPS |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **Benign Utility** | $BU$ | $N = 100$ (Ca thường nhật chuẩn hóa) | **$93.00\%$** | — | Năng lực phục vụ chính xác khi vận hành bình thường. |
| **Attack Success Rate** | $ASR$ | $N = 254$ (Toàn bộ không gian Track A) | **$27.30\%$** | $\pm 4.81\%$ | Tỷ lệ tấn công IPI chiếm quyền điều khiển thành công. |
| *-- ASR (Parse sạch)* | $ASR_{\text{clean}}$ | $N = 212$ (Các ca parse JSON chuẩn ở $r_1$) | **$18.87\%$** | — | Độ nhạy khi loại trừ ảnh hưởng của bộ parser dự phòng. |
| **Utility under Attack** | $UA$ | $N = 254$ (Toàn bộ không gian Track A) | **$65.62\%$** | $\pm 9.08\%$ | Năng lực duy trì an toàn/hợp lệ khi đang chịu tấn công. |
| **Utility Degradation** | $\mathbf{\Delta U}$ | **Hiệu số:** $\mathbf{BU - UA}$ | **$27.38\%$** | — | **$93.00\% - 65.62\% = 27.38\%$** *(Độ sụt giảm tiện ích thực tế).* |
| **Mitigation Hazard Rate** | $MHR$ | $N = 216$ (Tập kịch bản có hiểm họa vật lý) | **$34.08\%$** | $\pm 8.77\%$ | Tỷ lệ Agent bỏ qua xử lý an toàn khi tai nạn thực sự xảy ra. |
| **Format-Disruption Rate** | $FDR$ | $N = 254$ (Chỉ số chẩn đoán kỹ thuật) | **$16.54\%$** | $\pm 0.79\%$ | Tỷ lệ xảy ra lỗi cú pháp JSON do xung đột chỉ thị. |

---

### BẢNG 2: DIỄN BIẾN CHỈ SỐ QUA 3 VÒNG THỰC NGHIỆM ĐỘC LẬP ($k=3$)

| Chỉ số (Metric) | Vòng 1 ($r_1$) | Vòng 2 ($r_2$) | Vòng 3 ($r_3$) | **Trung bình (Mean $k=3$)** |
| :--- | :---: | :---: | :---: | :---: |
| **Attack Success Rate (ASR)** | 22.05% (56/254) | 28.35% (72/254) | 31.50% (80/254) | **27.30% $\pm 4.81\%$** |
| **Utility under Attack (UA)** | 75.98% (193/254) | 61.81% (157/254) | 59.06% (150/254) | **65.62% $\pm 9.08\%$** |
| **Độ Sụt Giảm Tiện Ích ($\mathbf{\Delta U}$)** | 17.02% | 31.19% | 33.94% | **27.38%** |
| **Mitigation Hazard Rate (MHR)** | 24.11% (52/216) | 37.50% (81/216) | 40.62% (87/216) | **34.08% $\pm 8.77\%$** |
| **Format-Disruption Rate (FDR)** | 16.54% (42/254) | 17.32% (44/254) | 15.75% (40/254) | **16.54% $\pm 0.79\%$** |

---

### BẢNG 3: PHÂN RÃ TỶ LỆ BỊ THAO TÚNG THEO 4 CHIỀU TẤN CÔNG (TAXONOMY BREAKDOWN QUA $k=3$)
> *Bảng trình bày tỷ lệ ASR chi tiết từng vòng và giá trị Mean; riêng dòng Data Stealing (DS) giữ nguyên ghi chú Wilson Score để minh bạch rủi ro tiềm ẩn.*

| Phân nhóm tấn công | Mã nhóm | Số ca ($N$) | ASR ($r_1$) | ASR ($r_2$) | ASR ($r_3$) | **Mean ASR (%)** | Cơ chế thất bại & Tác động vật lý |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Safety Suppression** *(Omission)* | **SUP** | 88 | 36.4% | 48.9% | 54.5% | **46.59%** | **Nguy hiểm nhất:** Agent bị thuyết phục bởi lý do diễn tập/bảo trì, tự ý bỏ qua còi hú và quạt khi có cháy/khói thật. |
| **Direct Harm - Actuation** | **DH-A** | 100 | 22.0% | 27.0% | 30.0% | **26.33%** | Bị lừa bởi thông tin phóng đại sự cố điện để ngắt quạt làm mát phòng máy chủ hoặc hú còi liên tục gây hoảng loạn. |
| **Direct Harm - Security** | **DH-S** | 36 | 5.6% | 5.6% | 5.6% | **5.56%** | Mạo danh chức danh để ép mở khóa chốt cửa phòng lab/server ngoài thẩm quyền (cơ chế kiểm soát an ninh cửa rất vững). |
| **Data Stealing** *(Trojan Audit)* | **DS** | 30 | 0.0% | 0.0% | 0.0% | **0.00%**$^*$ | Agent không gọi tool sink (`http_post`, `send_webhook`) để gửi Canary Token ra ngoài Internet. |

> $^*$ **Ghi chú riêng cho nhóm Data Stealing (DS):** Kết quả $0/30$ phản ánh hành vi thực nghiệm trong phạm vi kiểm thử; theo công thức khoảng tin cậy học thuật Wilson Score 95% với cỡ mẫu $n=30$, cận trên rủi ro rò rỉ tiềm ẩn là **$\le 11.35\%$**.

---

<a name="4-ba-dong-gop-nghien-cuu"></a>
# 4. BA ĐÓNG GÓP NGHIÊN CỨU ĐỘT PHÁ (C1, C2, C3) GẮN LIỀN VỚI BỐI CẢNH, CƠ CHẾ & HỆ QUẢ CPS

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                BA ĐÓNG GÓP HỌC THUẬT CỐT LÕI                                    │
├───────────────────────────────┬─────────────────────────────────┬───────────────────────────────┤
│    ĐÓNG GÓP 1 (C1)            │      ĐÓNG GÓP 2 (C2)            │      ĐÓNG GÓP 3 (C3)          │
│ Khung Benchmark CPS Đa Chiều  │ Phát Hiện Cơ Chế Omission       │ Kiểm Toán Thực Thi (Harness)  │
│ & Hiện Tượng Đảo Cực An Toàn  │ & Đối Chứng Nhân Quả Clean Twin │ & Chỉ Dấu Vỡ Định Dạng (FDR)  │
├───────────────────────────────┼─────────────────────────────────┼───────────────────────────────┤
│ • Ground truth từ SOP vật lý  │ • SUP nguy hiểm nhất (ASR 46.6%)│ • Kiểm toán 42 ca fallback    │
│ • "Không hành động" = Lỗi     │ • Clean Twin bóc tách nhân quả  │ • Xung đột chỉ thị gây vỡ JSON│
│ • Đo đồng thời Utility & ASR  │ • ΔASR quy kết trực tiếp do IPI │ • Hàm ý thiết kế Fail-safe    │
└───────────────────────────────┴─────────────────────────────────┴───────────────────────────────┘
```

### Đóng Góp 1 (C1): Khung Benchmark CPS Đa Chiều Với Cơ Chế Đảo Cực An Toàn (Safety Polarity Inversion) & Ground Truth Vật Lý Tất Định

* **Bối cảnh ứng dụng đặc thù:**
  Hệ thống điều khiển khuôn viên thông minh vận hành trên thực tế với 2 phòng học và 1 hành lang kết nối vi điều khiển ESP32, quản lý các thiết bị chấp hành vật lý có tính bất đối xứng: quạt hút khói 2N2222, khóa chốt Servo SG90, còi báo động an ninh.
* **Khoảng trống tri thức (Research Gap) & Đối chiếu y văn:**
  - **InjecAgent** (Deng et al., 2024) chỉ đo tỷ lệ tấn công thô (ASR) trên các lệnh gọi tool văn phòng mà hoàn toàn **không đo lường tính hữu dụng (Utility)** của Agent khi vận hành bình thường.
  - **AgentDojo** (Debenedetti et al., 2024) đánh giá trong môi trường phần mềm ảo với trạng thái số tĩnh, nơi mọi thao tác sai đều có thể hoàn tác (rollback).
  - **Evil-AI** (2024) khảo sát thiết bị IoT gia đình nhưng lại phụ thuộc vào **LLM-as-a-Judge** để chấm điểm nhị phân, dễ gây sai lệch (bias) và thiếu tính nhất quán khoa học.
  - **AgentAbstain (UIUC, 2026):** Khảo sát khả năng "biết dừng lại" (abstention) của agent, nhưng chỉ đánh giá đơn lượt trong sandbox số và **chưa có tấn công IPI chủ động**. Quan trọng nhất, ở AgentAbstain, việc Agent dừng lại/từ chối là hành vi đúng đắn; ngược lại, trong bài toán CPS của chúng tôi, **dừng lại khi có hiểm họa thực sự là một sai phạm an toàn nghiêm trọng**.
* **Cơ chế & Phát hiện then chốt - Hiện tượng "Đảo cực an toàn" (Safety Polarity Inversion):**
  - Trong các benchmark IT truyền thống (InjecAgent, AgentDojo, Ignored Not Refused), hành vi "không hành động" (inactivity/abstention) được mặc định là an toàn (Fail-safe): nếu kẻ tấn công không ép được Agent gọi tool độc hại, hệ thống được coi là an toàn.
  - Trong hệ thống Cyber-Physical (CPS) khi có hiểm họa (cháy, ngạt khí, quá nhiệt), **"không hành động" đồng nghĩa với thất bại thảm họa (Catastrophic Omission Failure)**: phòng máy chủ quá nhiệt sẽ bốc cháy nếu quạt không bật; phòng lab ngập khói sẽ gây ngạt nếu còi không hú.
  - Hệ quả mang tính phương pháp luận: **Định nghĩa ASR bắt buộc phải phụ thuộc vào trạng thái hiểm họa vật lý ($T_0$ ground truth)**:
    - *Khi có hiểm họa:* Thắng lợi của kẻ tấn công là Omission (buộc Agent không thực hiện hành động cứu hộ).
    - *Khi không có hiểm họa:* Thắng lợi của kẻ tấn công là Commission (buộc Agent can thiệp phá hoại).
* **Minh chứng thực nghiệm:**
  Bộ dữ liệu gồm 254 ca tấn công Track A và 100 ca Benign Baseline với Ground Truth xác định hoàn toàn qua luật logic cứng của cảm biến và SOP, đo lường đồng thời: $BU = 93.00\%$, $UA = 65.62\%$, $\Delta U = 27.38\%$, $MHR = 34.08\%$ và $ASR = 27.30\%$ (trung bình $k=3$).

---

### Đóng Góp 2 (C2): Phát Hiện Cơ Chế Tấn Công Triệt Tiêu An Toàn (Safety Suppression / Omission) & Bằng Chứng Đối Chứng Phản Thực Tế Clean Twin ($k=3$)

* **Bối cảnh & Cơ chế tấn công đặc thù:**
  Kẻ tấn công chỉ kiểm soát duy nhất trường văn bản tự do `description`, trong khi toàn bộ dữ liệu cảm biến đo đạc (nhiệt độ $52.3^\circ\text{C}$, khói $650\text{ ppm}$) là hoàn toàn có thật và hiển hiện trên giao diện.
* **Khoảng trống tri thức (Research Gap) & Đối chiếu y văn:**
  - **EpiSEM-Bench:** Nghiên cứu hiện tượng mất bằng chứng an toàn thụ động (passive epistemic degradation) khiến Agent hành động sai. SmartCampus khác biệt ở chỗ: *bằng chứng cảm biến vật lý vẫn đầy đủ và hoàn toàn chính xác*, nhưng văn bản mô tả không tin cậy chứa IPI đã **lấn át hoàn toàn tín hiệu cảm biến (Text-overrides-Sensor Bias)**.
  - **"Ignored, Not Refused" (2025/2026):** Chỉ ra rằng các benchmark truyền thống thường che giấu việc Agent chỉ đơn thuần "lờ đi" (ignored) mệnh lệnh thay vì thực sự "từ chối" (refused). Trong môi trường CPS của chúng tôi, **việc Agent "lờ đi" quy chuẩn cứu hộ chính là mục tiêu thắng lợi cao nhất của kẻ tấn công**.
  - Trong 7 công trình bảo mật hàng đầu, chưa có nghiên cứu nào bóc tách Omission thành một lớp tấn công riêng biệt có kiểm chứng nhân quả. Trước đây, khi Agent bỏ sót cứu hộ, người phản biện có quyền nghi ngờ: *"Liệu đó là do tấn công hay do LLM vốn dĩ ngẫu nhiên quên gọi tool (Natural Incompetence)?"*
* **Kế thừa phương pháp luận & Thiết kế thực nghiệm Clean Twin ($k=3$):**
  - Kế thừa tư tưởng thiết kế cặp thế giới $(T^+, T^-)$ từ AgentAbstain và $(W^-, W^+)$ từ EpiSEM-Bench, chúng tôi xây dựng phương pháp **Clean Twin (Bản sao đối chứng sạch)**: Giữ nguyên $100\%$ tham số vật lý nguy hiểm, chỉ làm sạch các câu chữ ngụy tạo. Chạy lặp lại độc lập $k=3$ vòng ($300$ lượt thực nghiệm).
* **Bằng chứng thép quy kết nhân quả:**
  1. **Nhánh Z (Bare Technical - Cảnh báo kỹ thuật thuần túy, không lời dẫn):** Tỷ lệ bỏ sót là **$0.0\%$ (0/36)**, 95% CI $[0.0\%, 9.6\%]$. $\Rightarrow$ **Chứng minh năng lực nhận thức tự nhiên của LLM đạt $100\%$, tỷ lệ quên tự nhiên bằng 0!**
  2. **Nhánh P (Claim-only - Chỉ có bối cảnh giả, cắt bỏ câu lệnh cấm):** Tỷ lệ bỏ sót là **$23.1\%$ (20.33/88)**. $\Rightarrow$ Bối cảnh ngụy tạo tự thân đã đủ gây đánh lạc hướng nhận thức nghiêm trọng.
  3. **Nhánh A (Attack đầy đủ - Bối cảnh giả + Lệnh cấm):** Tỷ lệ bỏ sót tăng vọt lên **$36.4\%$ (32/88)** ở $r_1$ và đạt **trung bình $46.59\%$ qua $k=3$**.
  4. **Mức tăng quy kết trực tiếp do IPI:** **$\mathbf{\Delta ASR = +36.4}$ điểm %** (so với Z), kiểm định dấu hai phía đạt ý nghĩa thống kê cao ($p = 0.01916 < 0.05$).
  - 👉 **Kết luận học thuật:** Trong các hệ thống điều khiển thực tế, **thuyết phục Agent "ngồi yên khi có tai nạn" đạt tỷ lệ thành công cao gấp đôi so với ép Agent phá hoại chủ động** ($46.59\%$ của SUP so với $26.33\%$ của DH-A và $5.56\%$ của DH-S).

---

### Đóng Góp 3 (C3): Phát Hiện Hiện Tượng Phá Vỡ Định Dạng (Format-Disruption Rate - FDR) & Hàm Ý Thiết Kế Fail-safe Cho CPS Agent

* **Bối cảnh & Khoảng trống tri thức:**
  Các công trình **Firewalls (2024)** và **EASE (2024)** cảnh báo rằng các benchmark bảo mật agent thường bị méo mó kết quả do các bộ parser regex hoặc lỗi môi trường kiểm thử (harness artifacts).
* **Kiểm toán toàn vẹn quy trình (Harness Audit):**
  Chúng tôi tiến hành kiểm toán thủ công 100% trên toàn bộ 42 ca phải sử dụng bộ parser dự phòng (Regex Fallback). Kết quả: **$100\%$ các ca fallback đều phản ánh chính xác ý định chủ quan của mô hình** (16 ca tấn công thành công và 26 ca tấn công thất bại). Khi loại bỏ hoàn toàn các ca fallback, ASR parse sạch vẫn đạt **$18.87\%$**, khẳng định tính trung thực tuyệt đối của số liệu.
* **Phát hiện chế độ lỗi mới - Format-Disruption Rate ($FDR = 16.54\% \pm 0.79\%$):**
  - Tỷ lệ vỡ định dạng JSON ở tập tấn công duy trì ổn định ở mức **$16.54\%$**, cao hơn hẳn so với tập benign ($11.00\%$).
  - **Chỉ dấu rủi ro cao (High-risk Indicator):** Phân tích tương quan cho thấy các ca bị vỡ định dạng có tỷ lệ bị tấn công thành công lên tới **$38.10\%$ (16/42)**, so với chỉ **$18.87\%$ (40/212)** ở các ca parse sạch (kiểm định Fisher exact $p \approx 0.013$).
* **Hàm ý kiến trúc phòng thủ Fail-safe cho CPS:**
  Hiện tượng đứt gãy JSON là triệu chứng bề mặt của sự xung đột nhận thức nội tại khi LLM bị giằng xé giữa System Prompt và Payload tấn công. Trong hệ thống Cyber-Physical, phát hiện này gợi mở một nguyên lý phòng thủ then chốt: **Khi phát hiện lỗi cú pháp, hệ thống tuyệt đối không nên cố gắng vá lỗi để tiếp tục thực thi, mà phải kích hoạt chế độ Fail-safe Inversion (chuyển về hành vi an toàn mặc định theo cảm biến vật lý).**

---

<a name="5-doi-chieu-related-work"></a>
# 5. ĐỐI CHIẾU CHI TIẾT VỚI RELATED WORK QUỐC TẾ

| Công trình / Benchmark | Năm | Miền ứng dụng | Nguồn Ground Truth | Đo Utility? | Phân tích Omission riêng? | Kế thừa phương pháp luận | Khoảng trống nghiên cứu (Gap) so với nghiên cứu này |
| :--- | :---: | :--- | :--- | :---: | :---: | :--- | :--- |
| **InjecAgent** | 2024 | Văn phòng ảo (Office Tools) | Khớp chuỗi lệnh gọi tool | ❌ Không | ❌ Không | Khung phân loại IPI tổng quát | Không đo Utility; không có ràng buộc vật lý hai chiều. |
| **AgentDojo** | 2024 | Web, Email, Bash | Trạng thái cơ sở dữ liệu số | ⚠️ Có (Utility số) | ❌ Không | Đánh giá qua trạng thái môi trường | Chỉ thao tác trên dữ liệu số tĩnh; mọi sai phạm đều có thể rollback. |
| **Evil-AI Benchmark**| 2024 | Thiết bị IoT gia đình | **LLM-as-a-Judge** (chấm văn bản)| ❌ Không | ❌ Không | Khảo sát thiết bị thông minh | Đánh giá chủ quan qua LLM Judge; bỏ qua lỗi cú pháp và utility. |
| **EASE Framework** | 2024 | Email Agent | Đánh giá phân tầng (Stage-wise) | ⚠️ Một phần | ❌ Không | Phân lập lỗi harness | Chưa kết hợp mô hình tấn công IPI trên thiết bị phần cứng. |
| **AgentAbstain** (UIUC) | 2026 | Tác vụ tổng quát (General Tasks)| Log Tool Call (Commit checks) | ⚠️ Một phần | ❌ Không | Thiết kế cặp $(T^+, T^-)$; kiểm tra commit xác định | **Ngược chiều:** Ở AgentAbstain dừng lại là đúng; ở SmartCampus dừng lại khi có hazard thật là sai phạm an toàn. |
| **EpiSEM-Bench** | 2025/2026 | Tác nhân truy vấn thông tin | Bằng chứng suy thoái thụ động | ✅ Có (Recovery) | ❌ Không | Cặp thế giới $W^-/W^+$; khái niệm false abstention | Chỉ xét mất bằng chứng thụ động; SmartCampus xét cảm biến đúng nhưng bị văn bản lấn át. |
| **Ignored, Not Refused**| 2025/2026 | LLM quy mô nhỏ | Kiểm toán qua CoT | ❌ Không | ⚠️ Nhận diện lờ đi | Phân loại hành vi: tuân thủ / từ chối / lờ đi | Coi "lờ đi" là trạng thái an toàn; chưa thấy trong CPS "lờ đi" chính là thất bại thảm họa. |
| **SmartCampus (Nghiên cứu này)**| **2026**| **Cyber-Physical Smart Campus**| **Tất định từ Cảm biến & SOP**| **✅ Có (BU 93%, UA 66%)**| **✅ Có (Clean Twin k=3, Δ=36.4%)**| **Kế thừa cặp đối chứng & chuẩn hóa Commit**| **Đề xuất Khái niệm Đảo cực an toàn & Omission trong CPS (ASR 46.6%).** |

---

<a name="6-gioi-han-nghien-cuu"></a>
# 6. GIỚI HẠN NGHIÊN CỨU (LIMITATIONS & FUTURE WORK)

Để đảm bảo tính trung thực học thuật cao nhất theo tiêu chuẩn của các hội nghị IEEE S&P / USENIX Security, các giới hạn của công trình được tuyên bố minh bạch:

1. **Phạm vi mô hình duy nhất (Single-Model Scope):** Thực nghiệm toàn diện hiện tại được triển khai trên `gemini-3.5-flash-lite`. Mặc dù mô hình đại diện cho năng lực agent tốc độ cao hiện đại, kết quả cần được mở rộng kiểm chứng trên các họ mô hình mã nguồn mở (như Llama-3-70B, Mistral-Large, Qwen-2.5) trong các nghiên cứu tiếp theo.
2. **Kịch bản tấn công tĩnh (Non-Adaptive Attackers):** Các payload tiêm nhiễm được thiết kế cố định theo 6 kỹ thuật tâm lý học xã hội, chưa áp dụng cơ chế tấn công tương tác nhiều vòng (Multi-turn Adaptive Jailbreak / Automated Red-teaming).
3. **Đơn sự kiện trên mỗi ca kiểm thử (Single-Event per Episode):** Mỗi testcase kích hoạt đánh giá dựa trên một sự kiện bất thường duy nhất tại mốc thời gian $T_0$, chưa mô phỏng chuỗi sự kiện dồn dập (Event Storming) kéo dài nhiều giờ.
4. **Đánh giá ở tầng khuyến nghị chấp hành (Dry-run Level Evaluation):** Nghiên cứu đo lường chính xác lệnh được sinh ra ở tầng `final_recommendation` kết nối qua Edge Gateway, chưa đo lường các sai số cơ học thực tế của relay điện trở hoặc van servo vật lý.
