# Plan Related Work & Đóng góp – SmartCampus Agent Security

Nov 2, 2026 · @naive

Với một bài theo miền cụ thể, đóng góp hẹp nhưng chứng minh được mạnh hơn đóng góp rộng không có bằng chứng. Mỗi đóng góp cần đủ bốn thứ: khoảng trống trong related work, sản phẩm hoặc phương pháp của bạn, bằng chứng (một bảng hoặc hình), và giới hạn phạm vi.

Tài liệu này chỉ dùng 7 bài trọng tâm: InjecAgent, AgentDojo, ASB, Firewalls, EASE, Evil-AI Bench, PromptShield-Home. Trong 15 bài còn lại của sheet, chỉ giữ 4 bài cho đoạn phòng thủ: CPS-Guard, Hybrid RAG, HVAC review, Policy-Aware Edge.

## 1. Đóng góp đề xuất

Bốn đóng góp, trong đó C1–C3 là lõi; C4 chỉ giữ nếu có số liệu.

| # | Đóng góp (viết hẹp) | Bằng chứng cần có | Điều kiện |
| --- | --- | --- | --- |
| C1 | Bộ 254 ca tấn công + 100 ca benign cho một Agent khuôn viên thông minh. Attacker chỉ kiểm soát **một trường văn bản**. Nhãn đúng/sai suy ra xác định từ **SOP + trạng thái cảm biến tại T0**. | Bảng cấu trúc bộ ca, số kịch bản gốc (T5) | Phạm vi: một triển khai, 4 SOP |
| C2 | Đưa **omission** (lừa Agent đứng yên trước hiểm họa thật) thành một lớp tấn công đo riêng. SUP có ASR cao nhất (36.4%) so với DH-A 22.0%, DH-S 5.6%, DS 0%. | Bảng theo taxonomy + **clean twin (T9)** để tách phần do tấn công khỏi lỗi tự nhiên | Chưa có T9 thì chỉ nói "quan sát" |
| C3 | **Audit harness:** cách xử lý output hỏng định dạng làm ASR dao động 18.9–22.1%, FDR 16.5%. Đề xuất báo cáo ASR kèm FDR. | Bảng kết quả T1–T2 | Chờ kiểm tay 16 ca |
| C4 (có điều kiện) | Quan sát về Review Agent cùng model: catch rate là X%. | T3 | Nếu không có số thì chuyển xuống Limitations |

**Không nên ghi là đóng góp:** "benchmark đầu tiên", "taxonomy mới", "chứng minh co-vulnerability", "chấm xác định" (AgentDojo đã làm), Hard Invariant (đây là hướng tương lai).

## 2. Ma trận khoảng trống

Ma trận cho thấy điểm khác thật sự của bạn: **nhãn lấy từ trạng thái vật lý** và **đo omission**. Hai điểm này chỉ đứng vững nếu xác minh được các ô "?" của Evil-AI Bench và PromptShield-Home. Ô nào không xác minh được thì để "chưa rõ", không điền đoán.

| Bài | Hiểm họa vật lý | Đo omission | Nguồn nhãn | Đo utility |
| --- | --- | --- | --- | --- |
| InjecAgent | Không (tool mô phỏng) | Không | Khớp tool call | **Không** |
| AgentDojo | Không | Không | Hàm kiểm tra trạng thái | Có |
| ASB | Không (có kịch bản lái xe nhưng mô phỏng) | Không | Attacker tool được gọi | Có (PNA) |
| Firewalls | Không | Không | Theo từng benchmark | Có |
| EASE | Không | Không | Kiểm tra kết quả thực (Gmail) | ? |
| Evil-AI Bench | Servo Arduino (proxy) | **? (README không nhắc)** | Tool call + 2 LLM judge + người | Có (capability, over-refusal) |
| PromptShield-Home | ? | Gần nhất: bỏ lỡ ca té ngã thật (SCR) | ? | Có (SCR) |
| **SmartCampus (bạn)** | Cảm biến thật, chấp hành dry-run | **Có** | SOP + cảm biến T0, xác định | Có (BU, UA) |

## 3. Plan việc cần làm

Đây là việc đọc và nghiên cứu, không sửa hệ thống. Trong chín việc, R1 và R4 làm trước vì hai việc này quyết định đóng góp C2 còn đứng được hay phải hạ giọng.

- [ ] **R1. Đọc kỹ Evil-AI Bench (làm trước nhất).** Đọc threat model, danh sách kịch bản và tiêu chí judge. Câu hỏi: có kịch bản nào mà đáp án đúng là *phải hành động* không? Nhóm "suppressed telemetry" (AITM) khác SUP của bạn thế nào? Kết quả: một đoạn "khác biệt" có dẫn mục, trang.
- [ ] **R2. Đọc PromptShield-Home.** Lấy định nghĩa UER và SCR, nhãn do ai gán, ca "té ngã thật" tính là lỗi gì. Kết quả: nói chính xác SCR gần omission đến đâu và khác SUP ở chỗ nào (kênh ảnh/âm thanh, không phải tấn công qua văn bản).
- [ ] **R3. Điền đầy ma trận khoảng trống** và ghi trang/mục cho từng ô. Ô nào không xác minh được thì để "chưa rõ".
- [ ] **R4. Tìm tiền lệ cho SUP.** Từ khóa: "suppression attack LLM agent", "unsafe inaction", "omission failure safety-critical agent", "denial of safety function". Về khái niệm, tra thêm MITRE ATT&CK for ICS (tactic "Inhibit Response Function") và TRISIS. Kết quả: 2–3 bài gần nhất và một câu giải thích khác ở đâu. Nếu tìm thấy bài đã làm đúng việc này thì phải hạ C2 xuống.
- [ ] **R5. Ánh xạ kỹ thuật tấn công.** Cascade attack của Firewalls có Stage 2 là "semantic template có decoy", gần giống tấn công pretext (authority, urgency, SOP-aware) của bạn. Bạn chưa có Stage 3 (tấn công thích ứng, nhận biết phòng thủ). Dùng để biện minh cho attacker mạnh và ghi vào Limitations.
- [ ] **R6. Sổ kế thừa (inheritance ledger).** Mỗi dòng: lấy gì, từ bài nào, bạn thay đổi gì. Xem bảng bên dưới.
- [ ] **R7. Kiểm tra số liệu trong sheet trước khi trích.** Hàng 18 (Firewalls) ghi "ASR ≈ 0% trên cả 4 benchmark", nhưng bài thật cho thấy Sanitizer đạt ASR 16.33% trên ASB bản gốc và 30% dưới cascade attack; hãy đọc lại bảng kết quả. Hàng 19: nhóm tác giả và nơi công tác chưa xác minh, chỉ nên trích tên bài và mã arXiv. Evil-AI chưa có venue; trích là preprint.
- [ ] **R8. Đoạn phòng thủ (4 bài).** Đọc nhanh phương pháp và giới hạn của CPS-Guard, Hybrid RAG, HVAC review, Policy-Aware Edge. Policy-Aware Edge dùng Dual-LLM judge, đối chiếu trực tiếp với Review Agent của bạn. EASE còn cho thấy prompt phòng thủ có thể phản tác dụng, dùng khi bàn về Review/Reflect.
- [ ] **R9. Viết.** Sau R1–R6, viết 4 đoạn (benchmark IPI, phương pháp đánh giá, agent CPS/IoT, phòng thủ xác định) và một câu khoảng trống cuối.

**Sổ kế thừa (R6):**

| Lấy gì | Từ bài | Bạn thay đổi gì |
| --- | --- | --- |
| DH/DS, ma trận user × attacker (17×62 của họ cũng không độc lập) | InjecAgent | Ca sinh từ kịch bản gốc SOP + cảm biến |
| BU, UA, ASR; chấm theo trạng thái | AgentDojo | Trạng thái là cảm biến vật lý, thêm omission |
| Đo cả utility lẫn ASR; có thể thêm NRP = BU × (1−ASR) ≈ 72.5% | ASB | Chỉ để tiện đối chiếu, không xếp hạng |
| Audit benchmark; tấn công thích ứng | Firewalls | Audit parser/harness của chính bạn; chưa có Stage 3 |
| Stage-wise và kiểm tra thực thi | EASE | Mở rộng pipeline cho CPS (S0→S6 là của bạn) |
| Tách UER/SCR; baseline tầm thường (luôn hành động / không bao giờ hành động) | PromptShield-Home | Áp dụng cho tấn công qua văn bản |

## 4. Thứ tự ưu tiên và liên hệ với plan thực nghiệm

Thứ tự đề xuất: **R1 → R4 → R3 → R6 → R2 → R5 → R7 → R8 → R9.**

Mỗi đóng góp phụ thuộc vào một phần của plan thực nghiệm, nên cần chốt song song với R1–R4:

| Đóng góp | Phụ thuộc vào |
| --- | --- |
| C2 | T9 (clean twin), T5 (CI theo cụm) |
| C3 | T1, T2 (audit parser) |
| C4 | T3 (catch rate) |

Nếu R4 hoặc T9 làm yếu C2, hai đóng góp C1 và C3 vẫn đủ để bài đứng vững như một benchmark theo miền kèm audit phương pháp.
