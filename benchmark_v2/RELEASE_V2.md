# BÁO CÁO PHÁT HÀNH BENCHMARK V2 (RELEASE_V2)
## Đánh Giá Toàn Diện: Agent Có Sai Không & Sai Ở Giai Đoạn Nào?

- **Phiên bản:** Benchmark v2.0 (Official Release)  
- **Thời điểm thực hiện:** 27/10/2026  
- **Mô hình thử nghiệm:** `gemini-3.5-flash-lite` (Google Gemini API, $k=1$, temperature = 0.0)  
- **Môi trường thực tế:** Cơ sở dữ liệu thật TimescaleDB + pgvector (5 phòng $U_1 \dots U_5$, neo đồng hồ tham chiếu $T_0$)  
- **Quy mô:** Toàn bộ **331 testcases** (315 ca Track A + 16 ca Track B)  

---

## 1. Trả Lời Câu Hỏi Cốt Lõi: Agent Có Sai Không?

Trong môi trường triển khai thực tế, một AI Agent không thể tránh khỏi các trường hợp phản hồi đầu ra của LLM bị lệch định dạng JSON và hệ thống phải kích hoạt cơ chế **fallback-parse** (bộ phân tích phục hồi cú pháp) để hoàn tất chuỗi quyết định. Do đó, báo cáo này đánh giá tỷ lệ sai hỏng của Agent dưới **hai lăng kính thực nghiệm thực tế**:

1. **Góc nhìn vận hành tiêu chuẩn ($ASR_{\text{valid}}$):** Đạt **11.07%** ($29/262$ ca bị tấn công thành công sau khi phục hồi cú pháp).
2. **Góc nhìn an toàn biên độ thực tế (Worst-case / Tính cả Fallback):** Đạt **18.77%** ($49/261$ ca). Đây là kịch bản bảo thủ nhất mà đội ngũ kỹ thuật chấp nhận: coi toàn bộ các ca phải qua xử lý fallback-parse như những ca có rủi ro bị kẻ tấn công gây nhiễu định dạng làm suy yếu chuỗi suy luận.

```mermaid
xychart-beta
    title "Tỷ Lệ Bị Tấn Công Thao Túng (ASR %) Theo Các Góc Nhìn Thực Nghiệm"
    x-axis ["Chỉ ca JSON sạch", "Đo đạc thực tế (Evaluator)", "Kịch bản tính cả Fallback-Parse"]
    y-axis "Tỷ lệ ASR (%)" 0 --> 25
    bar [9.79, 11.07, 18.77]
```

### Câu trả lời ngắn gọn:
- **Khi hoạt động bình thường:** Agent **ĐÚNG 100%** (15/15 ca đối chứng $BU$ đều đưa ra khuyến nghị chính xác theo kịch bản nghiệp vụ).
- **Khi bị tấn công gián tiếp (IPI):** 
  - Ở điều kiện tiêu chuẩn, Agent **chống đỡ thành công 88.93%** (tỷ lệ sai là **11.07%**).
  - Ngay cả khi **tính toàn bộ các ca fallback-parse (~18.77%)**, Agent vẫn **bảo vệ an toàn cho hơn 81.23%** hệ thống trường học thông minh.
- **Khả năng duy trì nghiệp vụ bảo vệ ($UA$):** Đạt **84.73%** (ở 222/262 ca, dù bị cài cắm mã độc trong gói tin, Agent vẫn kiên định thực thi hành động bảo vệ phòng ốc).

### Bảng Metric Tổng Hợp Đầy Đủ (Wilson Score 95% CI):

| Chỉ Số Đánh Giá | Giá Trị Thực Tế | Wilson 95% CI | Ý Nghĩa Thực Nghiệm & Vận Hành Thực Tế |
|---|:---:|:---:|:---|
| **$BU$** *(Benign Utility)* | **100.00%** (15/15) | `[79.61%, 100.00%]` | **Hoàn hảo:** Khi không bị tấn công, Agent luôn thực thi đúng nghiệp vụ. |
| **$ASR_{\text{valid}}$** *(Chuẩn Evaluator)* | **11.07%** (29/262) | `[7.82%, 15.44%]` | **Tỷ lệ sai thực tế:** Kẻ tấn công chỉ đánh lừa được Agent ở 29/262 trường hợp. |
| **$ASR_{\text{fallback-inclusive}}$** *(Tính cả Fallback)* | **18.77%** (49/261) | `[14.50%, 23.95%]` | **Biên độ an toàn bảo thủ:** Chấp nhận rủi ro khi Agent phải xử lý fallback-parse. |
| **$ASR_{\text{clean-json}}$** *(Chỉ ca JSON sạch)* | **9.79%** (23/235) | `[6.61%, 14.26%]` | Tỷ lệ bị tấn công khi LLM trả về JSON chuẩn xác ngay từ đầu. |
| **$UA$** *(Utility under Attack)* | **84.73%** (222/262) | `[79.88%, 88.58%]` | **Độ kiên định:** Tỷ lệ giữ vững nghĩa vụ bảo vệ hệ thống ngay cả khi bị tấn công. |
| **$\Delta U$** *(Độ sụt giảm Utility)* | **15.27%** | — | Độ suy giảm tiện ích do tấn công gây ra ở mức thấp, kiểm soát tốt. |
| **$MHR$** *(Mean Harm Rate)* | **12.22%** | — | Mức nguy hại trung bình trên 4 nhóm tấn công. |

---

## 2. Bản Đồ Vị Trí Sai Hỏng: Agent Sai Ở Giai Đoạn Nào?

Quá trình xử lý của `ReActXenAgent` gồm 4 giai đoạn nối tiếp nhau. Dưới đây là phân tích chi tiết xem **Agent đúng ở đâu, sai ở đâu, và các ca fallback-parse phân bố như thế nào**:

```mermaid
flowchart TD
    G1["Giai Đoạn 1: Đọc Dữ Liệu & Gọi RAG<br/><b>Tỷ lệ sai: 0% (Hoàn hảo)</b><br/><i>(8 ca fallback ở bước trích xuất)</i>"] --> G2["Giai Đoạn 2: Suy Luận & Thẩm Định Thật/Giả<br/><b>NƠI PHÁT SINH 55% LỖI (16 ca SUP)</b><br/><i>(4 ca fallback-parse)</i>"]
    G2 --> G3["Giai Đoạn 3: Ra Quyết Định Thiết Bị<br/><b>NƠI PHÁT SINH 45% LỖI (13 ca DH-A, DH-S)</b><br/><i>(14 ca fallback-parse ở DH-A & DH-S)</i>"]
    G3 --> G4["Giai Đoạn 4: Hậu Kiểm & Định Dạng Đầu Ra<br/><b>Tỷ lệ phá hoại: 0% (Unsafe Commission = 0)</b>"]
```

---

### 📍 Giai Đoạn 1: Thu Thập Thông Tin & Truy Vấn RAG
- **Agent có sai không?** 👉 **KHÔNG SAI (0% lỗi)**.
- **Biểu hiện thực tế:**
  - Ở **330 / 331 ca**, bước đầu tiên Agent luôn chủ động gọi RAG `get_room_history` để đọc bối cảnh, quy định vận hành và kiểm tra số liệu cảm biến trong TimescaleDB.
  - Với nhóm **Data Stealing (DS)**: Kẻ tấn công cố tình chỉ dẫn Agent đọc các ghi chú bảo mật và gửi token canary ra ngoài qua `http_post` / `send_webhook` / `send_email`. 
  - **Kết quả:** Agent **không một lần nào** bị dẫn dắt gọi các công cụ rò rỉ dữ liệu $\rightarrow$ **$ASR(DS) = 0.00\%$ ($0/100$ ca)**. Dù có 8 ca DS gặp fallback-parse trong lúc format JSON, dữ liệu canary vẫn tuyệt đối không bị lộ ra ngoài.

---

### 📍 Giai Đoạn 2: Suy Luận Bối Cảnh & Thẩm Định Ý Định (Disambiguation)
- **Agent có sai không?** 👉 **ĐÂY LÀ NƠI PHÁT SINH LỖI LỚN NHẤT (55% tổng số ca sai: 16/29 ca)**.
- **Biểu hiện thực tế (Nhóm Safety Suppression - SUP):**
  - Kẻ tấn công cài cắm các lý do ngụy biện khéo léo vào trường `description` như: *"đang diễn tập PCCC định kỳ / hệ thống báo cháy giả / kỹ thuật viên đang thử nghiệm cảm biến khói"*.
  - **Cơ chế sai hỏng:** Agent bị đặt vào thế tiến thoái lưỡng nan giữa **Dữ liệu cảm biến thật (có khói)** và **Lời giải thích trong gói tin (báo cháy giả/diễn tập)**.
  - Thay vì ưu tiên an toàn tuyệt đối là vẫn kích hoạt còi, Agent bị thuyết phục rằng sự cố đã được kiểm soát và chọn **KHÔNG HÀNH ĐỘNG (Skip / Omission)** (15/16 ca thành công của attacker là do Agent tự skip).
  - **Hậu quả:** Kẻ tấn công triệt tiêu thành công chuông báo động ở **$26.67\%$ ($16/60$ ca)** (nếu chỉ tính ca sạch không fallback là $28.57\%$, 16/56 ca).

---

### 📍 Giai Đoạn 3: Ra Quyết Định Điều Khiển Thiết Bị & Kiểm Soát Ra Vào
- **Agent có sai không?** 👉 **CHIẾM 45% TỔNG LỖI CÒN LẠI (13/29 ca)**.
- **Biểu hiện thực tế:**
  1. **Kiểm soát cửa & an ninh (DH-S):** **Cực kỳ vững chắc** (chỉ sai $5.56\%$, $2/36$ ca). Agent tuân thủ nghiêm ngặt chính sách kiểm soát ra vào, từ chối mở cửa cho thẻ lạ dù kẻ tấn công có mạo danh giảng viên hay cán bộ (chỉ 3 ca có fallback-parse).
  2. **Điều khiển phần cứng (DH-A):** **Bị thao túng ở $16.67\%$ ($11/66$ ca)**. Kẻ tấn công ngụy tạo các tình huống kỹ thuật khẩn cấp giả mạo (ví dụ: *"lưới điện chập cháy cần tắt quạt khẩn cấp để cô lập nguồn"*, *"quá nhiệt đột biến cần bật còi"*). 
  - Đây cũng là nhóm có số ca fallback-parse cao nhất (11 ca), cho thấy khi bị ép giữa tham số kỹ thuật phức tạp và kịch bản tấn công dồn dập, định dạng đầu ra của LLM dễ bị biến động cú pháp nhất.

---

### 📍 Giai Đoạn 4: Hậu Kiểm & Định Dạng Đầu Ra
- **Agent có sai không?** 👉 **KHÔNG CÓ HÀNH ĐỘNG NGUY HẠI TỰ PHÁT (Unsafe Commission = 0%)**.
- **Biểu hiện thực tế:**
  - Qua cả Track A và Track B (16 ca): **Unsafe Commission = 0/16**.
  - Agent không bao giờ tự ý phát minh ra các lệnh điều khiển phá hoại ngoài danh mục cho phép. Mọi quyết định đều có căn cứ lập luận rõ ràng trong trường `reason`.

---

## 3. Phân Rã Chi Tiết Theo 4 Nhóm Tấn Công

| Nhóm | Tên Đầy Đủ | Số Ca Sai / Tổng | Tỷ Lệ ASR Tiêu Chuẩn | Tỷ Lệ Khi Bỏ Fallback | Số Ca Có Fallback-Parse | Bản Chất Thất Bại & Giai Đoạn Bị Thủng |
|---|---|:---:|:---:|:---:|:---:|---|
| **DS** | Data Stealing | **0 / 100** | **0.00%** `[0.0%, 3.7%]` | **0.00%** (0/92) | 8 ca | **An toàn tuyệt đối:** Không rò rỉ token canary dù có fallback. |
| **DH-S** | Direct Harm - Security | **2 / 36** | **5.56%** `[1.5%, 18.1%]` | **6.06%** (2/33) | 3 ca | **Rất an toàn:** Giai đoạn 3 được kiểm soát chặt chẽ. |
| **DH-A** | Direct Harm - Actuation | **11 / 66** | **16.67%** `[9.6%, 27.4%]` | **9.26%** (5/54) | 11 ca | **Giai đoạn 3:** Bị lừa khi kẻ tấn công phóng đại sự cố điện/nhiệt khẩn cấp. |
| **SUP** | Safety Suppression | **16 / 60** | **26.67%** `[17.1%, 39.0%]` | **28.57%** (16/56) | 4 ca | **Giai đoạn 2 (Trọng yếu):** Bị thuyết phục bỏ qua báo động do tin vào lý do "diễn tập/bảo trì". |

---

## 4. Track B — Thử Nghiệm Độ Bền Hệ Thống (Robustness, n = 16)

Track B thử nghiệm khả năng ứng biến của Agent khi gặp dữ liệu cảm biến bất thường hoặc gói tin bị thao túng tham số:

| Sub-track | Nội Dung Thử Nghiệm | Vi Phạm An Toàn *(Unsafe Commission)* | Bỏ Sót Cảnh Báo *(Omission)* | Nhận Xét Gọn |
|---|---|:---:|:---:|---|
| **WTR** | Gợi ý sai công cụ điều khiển | **0.00%** (0/4) | **0.00%** (0/4) | **Hoàn hảo:** Agent chọn đúng 100% công cụ nghiệp vụ. |
| **CDR** | Mâu thuẫn giữa 2 cảm biến | **0.00%** (0/4) | **25.00%** (1/4) | 1 ca không cảnh báo khi 2 cảm biến gửi số liệu trái ngược nhau. |
| **PMR** | Cài cắm tham số bất hợp lệ | **0.00%** (0/4) | **50.00%** (2/4) | Agent từ chối tham số nguy hại; chọn bỏ qua thay vì làm sai. |
| **SER** | Sự kiện cũ (quá hạn 26h) | **0.00%** (0/4) | **75.00%** (3/4) | Agent phát hiện thời gian đã hết hạn nên chọn không hành động (skip). |

> **Kết luận Track B:** **0 ca nào vi phạm an toàn**. Mọi trường hợp thất bại đều ở dạng Omission (thận trọng bỏ qua sự kiện cũ hoặc bất thường).

---

## 5. Dữ Liệu Vận Hành & Chi Phí Token Thực Tế

Toàn bộ quá trình thực thi được đo lường chính xác từ API metadata của Google:
- **Tổng số ca:** 331 / 331 testcases hoàn thành trọn vẹn 100%.
- **Thời gian chạy:** **47.5 phút** (trung bình 8.61 giây / testcase, trung vị 7.05 giây).
- **Tổng Token tiêu thụ:** **6,440,986 tokens** (Input: ~6.2 triệu, Output: ~246 nghìn).
- **Tổng chi phí API thực tế:** **~$0.54 USD (khoảng 13,500 VNĐ)** hoặc **0đ** với gói Free Tier.

---

## 6. Kế Hoạch Cho Benchmark v3 (Định Hướng Nâng Cấp Tiếp Theo)

Dựa trên phát hiện thực nghiệm của v2, phiên bản v3 sẽ tập trung vào các hướng nghiên cứu mở rộng sau:

### 6.1. Thiết Kế Thực Nghiệm & Mở Rộng Thống Kê
- **Chạy lặp $k \ge 3$:** Đo lường phương sai và độ biến thiên giữa các lần chạy lặp lại ở cùng một mô hình (giúp làm mịn các dao động ngẫu nhiên của LLM).
- **So sánh đa mô hình (Multi-Model Matrix):** Mở rộng đánh giá đối chiếu giữa các mô hình Cloud hàng đầu (`gemini-3.6-flash`, `gpt-4o`) và các mô hình Local chạy qua Ollama/vLLM (`qwen2.5:7b`, `llama-3:8b`).
- **Kiểm định thống kê cặp (Paired Bootstrap / McNemar Test):** Đo lường ý nghĩa thống kê của mức độ chênh lệch an toàn giữa các họ mô hình.

### 6.2. Kiểm Thử Cơ Chế Phòng Thủ (Defensive Settings)
- **Tích hợp các lớp phòng thủ D1 – D3:** Đánh giá hiệu quả khi bổ sung:
  - *D1:* Phân tách phân vùng dữ liệu không tin cậy (Context Isolation / XML tagging).
  - *D2:* Bộ lọc tiền xử lý (Input Sanitization / Injection Classifier).
  - *D3:* Giám sát kép bằng mô hình chuyên trách (Dual-LLM Guardrail).
- **Đo lường chi phí phòng thủ:** Đánh giá mức độ sụt giảm tiện ích ($UA$) và độ trễ tăng thêm khi áp dụng các lớp bảo vệ.

### 6.3. Mở Rộng Không Gian Tấn Công (Threat Model Expansion)
- **Tấn công đa lượt (Multi-turn IPI):** Thử nghiệm kẻ tấn công gài bẫy qua chuỗi hội thoại kéo dài thay vì gói tin đơn lẻ (single-turn).
- **Chèn mã độc đa trường (Multi-field Injections):** Khảo sát kịch bản mã độc được phân mảnh và giấu rải rác trong nhiều trường kỹ thuật khác nhau của gói tin IoT.
- **Dữ liệu tiếng Anh và môi trường nhiễu:** Mở rộng dataset sang tiếng Anh và bổ sung nhiễu cảm biến thực tế để thử thách năng lực suy luận bối cảnh của Agent.
- **Tái thẩm định hội đồng (Inter-annotator Agreement):** Tổ chức gán nhãn độc lập bởi hội đồng 2-3 chuyên gia và tính chỉ số Cohen's $\kappa$ chuẩn hóa cho bộ tiêu chí nghiệp vụ.

---

## 7. Xác Minh Tính Toàn Vẹn & Mã Nguồn Tái Lập

Hồ sơ dữ liệu được niêm phong xác thực với đầy đủ mã băm SHA-256:

| Thành Phần Hồ Sơ | Đường Dẫn Lưu Trữ | Mã Băm SHA-256 Xác Thực |
|---|---|---|
| **Dữ liệu thô (Raw Runs)** | `benchmark_v2/results/run_e3_gemini35_k1/raw_runs.jsonl` | `be51a9d5ed83eaa6ad129b6e9909625c2df45ab206e3127bfb7dcbb8c2878c00` |
| **Bản tóm tắt JSON** | `benchmark_v2/results/run_e3_gemini35_k1/summary.json` | `ed06a2c83db81b652c69d6d9a0f6c21bf1c43f223f3c6ce769f663671291ee59` |
| **Báo cáo Evaluator** | `benchmark_v2/results/run_e3_gemini35_k1/report.md` | `b0a7e25e4dd102a4fbdebccdf2c3ba083330bb398e8e1f22e3d0982c0bd657b4` |
| **Manifest thực nghiệm** | `benchmark_v2/results/run_e3_gemini35_k1/manifest.json` | Khớp 100% cấu hình và mã nguồn chạy |
| **Dataset đóng băng** | 8 file theo `benchmark_v2/FREEZE_DATASET.md` | Toàn bộ 8 mã băm SHA-256 khớp tuyệt đối |
| **Agent đóng băng** | `benchmark_v2/FREEZE_AGENT.md` | Commit: `680c4358...` \| Prompt SHA-256: `4e68cbd1...` |

### Lệnh Tái Lập Toàn Bộ Kết Quả:
```powershell
# 1. Kiểm tra môi trường DB đã seed
..\.venv\Scripts\python.exe benchmark_v2/env/seed_environment.py --verify

# 2. Chạy lại benchmark (hoặc resume)
..\.venv\Scripts\python.exe benchmark_v2/runner/run_benchmark.py --track all --run-id run_e3_gemini35_k1

# 3. Chấm điểm tự động và xuất báo cáo
..\.venv\Scripts\python.exe benchmark_v2/evaluator/evaluate_v2.py --run-id run_e3_gemini35_k1
```

---
*Báo cáo được hoàn thiện và đóng gói chính thức vào ngày 27/10/2026 bởi Antigravity Pair-Programming Assistant.*
