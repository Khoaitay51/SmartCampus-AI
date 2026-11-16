# Plan hoàn thiện phương pháp luận – SmartCampus Agent Security

> Mục tiêu: sửa phần phương pháp luận, metric và cách trình bày báo cáo. **Không đập đi làm lại hệ thống.** Việc chạy lại tối đa là k=3.

## 0. Nguyên tắc

- Không sửa `app/agent/*`, không đổi prompt hay model. Chỉ sửa code đánh giá, script phân tích, thêm log.
- Mọi thay đổi cách chấm điểm phải được ghi lại, không sửa ngầm.
- Threat model (ghi rõ vào báo cáo): attacker **biết SOP công khai của trường**, **không biết** system prompt, code hay thiết kế Agent (black-box, SOP-aware).

## 1. Giữ nguyên

- Kiến trúc hệ thống, threat model (thêm giả định SOP), 4 taxonomy (DH-A, DH-S, SUP, DS).
- Ground truth xác định, không dùng LLM-as-judge.
- Số baseline BU = 93.00%, ASR = 22.05% (trình bày là "k=1, pilot" cho đến khi có k=3).
- Phần Limitations, hướng tiếp theo Hard Physical Invariant.

## 2. Phase 0 – Đóng băng (không chạy model)

- **T0.** Ghi commit hash, tham số model (temperature, seed), danh sách ca test.

## 3. Phase 1 – Phân tích trên log đã có (không cần chạy lại)

| # | Việc | Đầu ra |
|---|------|--------|
| T1 | **Audit parser fallback.** Với 42 ca fallback: lưu output thô, phân loại lý do parse hỏng, hành động parser trích ra. Kiểm tay 16 ca ASR qua fallback có đúng ý định của model không. Kiểm thêm mẫu ca fallback "không thành công" để bắt lỗi chiều ngược lại. | Bảng audit |
| T2 | **Quy tắc chấm khi parse hỏng hoàn toàn.** Output rỗng/không parse được thì chấm thế nào? Với SUP, "không hành động" có bị tính nhầm là tấn công thành công không? | Mô tả quy tắc + số ca bị ảnh hưởng |
| T3 | **Review/Reflect.** Từ log: catch rate của Review trên **mọi** ca Main Agent đề xuất sai (không chỉ 56 ca lọt), reject rate trên benign, Reflect sửa đúng hay củng cố sai. | Bảng catch rate |
| T4 | **Sửa định nghĩa số.** ΔU bản cũ = 100 − 82.06 = **17.94** (báo cáo ghi 10.94 là sai); định nghĩa "ASR-valid" (8 ca bị loại là gì); mẫu số 224 của MHR; phân loại 4 ca UNSPECIFIED; kiểm tra Critical = 32 vs SUP = 32; thêm bảng S0→S6 hoặc bỏ nhãn. | Bảng định nghĩa metric |
| T5 | **Cluster bootstrap.** Gán `scenario_id` (kịch bản gốc), thống kê số kịch bản, CI theo cụm (B=10000) cho BU, ASR, UA, MHR, ASR theo taxonomy. | CI mới + số kịch bản gốc |
| T6 | **ASR theo kỹ thuật và attacker profile** (naive / authority / urgency / SOP-aware), nếu ca có nhãn. | Bảng ASR theo kỹ thuật |
| T7 | **Phân bố confidence** của ca tấn công thành công so với ca sạch. | Biểu đồ/bảng |

Báo cáo ASR dưới dạng khoảng: **parse sạch (18.87%) → gồm fallback (22.05%)**, kèm Format-Disruption Rate = 42/254.

## 4. Phase 2 – Chạy thêm (chỉ đổi harness)

| # | Việc | Ghi chú |
|---|------|---------|
| T8 | **k=3** toàn bộ attack + benign, cùng tham số. Thêm log: `parse_mode`, output thô, verdict Review từng vòng. | Báo cáo ASR mean / any (có lần nào thành công) / all (lần nào cũng thành công) + độ lệch giữa các lần |
| T9 | **Clean twin.** Mỗi kịch bản gốc chạy với `description` trung tính (cùng trạng thái cảm biến), k=3. Tái dùng benign nếu benign đã cùng kịch bản. | **ASR do tấn công = tỷ lệ lỗi khi tiêm − tỷ lệ lỗi khi không tiêm**, nhất là SUP và DH-A |
| T10 | **Positive control cho DS.** 5–10 ca (Canary token, dry-run) chứng minh sink có thể bị kích hoạt trong cấu hình dễ hơn. | Nếu không kích hoạt được: ghi "DS chưa kiểm chứng được" thay vì "0% rò rỉ" |
| T11 (tùy chọn) | **Ablation Review bật/tắt**, chỉ khi đã có cờ cấu hình. | Nếu phải sửa code → chuyển sang future work. Review dùng model khác / không thấy `description` cũng để future work |

## 5. Phase 3 – Sửa báo cáo

**Thay đổi**
- "Review Agent độc lập" → "Review Agent (cùng model, cùng context)".
- "Chứng minh thực nghiệm co-vulnerability" → "quan sát", kèm catch rate (T3).
- "Gấp 2 lần do mã tiêm" → "tương quan" (38.1% [25.0, 53.2] vs 18.87% [14.2, 24.7]; chưa kiểm soát confounder).
- Claim tính mới → "theo hiểu biết của chúng tôi"; SUP dẫn nguồn khái niệm từ omission/commission và ICS (Inhibit Response Function).
- Confidence 0.35 → "quality gate, không phải lớp bảo mật"; thêm phân bố confidence (T7).
- "Unmitigated robustness" → "không có lớp cưỡng chế xác định".
- Thêm: giả định SOP-aware, bảng ASR theo kỹ thuật (T6), ASR dạng khoảng, CI cluster, bảng ASR do tấn công (T9).
- Sửa trích dẫn: Firewalls paper là arXiv 10/2025; tên đúng là AgentSentry (kiểm tra lại claim "ASR về 0%"); tự xác minh Evil-AI Bench và EASE; thêm PromptShield-Home (arXiv 2608.05495).
- Đóng góp chính nhấn: **oracle vật lý xác định** (gán nhãn không cần LLM-as-judge) và đo omission trong CPS.

**Bỏ**
- Phần MODE_PERMISSIONS và bug schema Policy Engine.
- Các từ "đầu tiên", "duy nhất", "chứng minh".
- Dùng Human-in-the-Loop để giảm nhẹ 22% (HITL chưa được đo; có automation bias).

**Thêm vào Limitations**
- Attack v2 được tinh chỉnh sau khi xem kết quả v1 trên cùng model, nên ASR có thể cao hơn mức tổng quát. Kết quả Qwen/Llama sau này là kiểm tra chuyển giao (out-of-sample).
- Clustered design, k nhỏ, 1 model.

## 6. Phase 4 – Sau khi thầy duyệt

Chạy Qwen-2.5-7B và Llama-3.1-8B với cùng harness. Lưu ý tỷ lệ fallback ở model nhỏ sẽ cao hơn nhiều, nên T1–T2 phải xong trước.

## 7. Thứ tự ưu tiên nếu thời gian ngắn

**T1–T2 → T9 → T3 → T5 → T8**

## 8. Prompt giao cho Antigravity

```
Bối cảnh: repo SmartCampus (ReActXenAgent) có bộ benchmark đánh giá tấn công
prompt injection (254 ca tấn công, 100 ca benign, k=1). Việc cần làm CHỈ nằm ở
phần đánh giá/phân tích.

RÀNG BUỘC: không sửa app/agent/*, không đổi prompt hay model. Chỉ sửa/thêm code
trong thư mục đánh giá. Trước khi làm, đọc repo và báo cáo cấu trúc, nơi log
trajectory, cách chấm ASR, parser fallback.

Việc cần làm:
1. Audit parser fallback: với mỗi ca có parse_mode=fallback, xuất output thô,
   lý do parse hỏng, hành động parser trích ra. Liệt kê riêng các ca ASR qua
   fallback để kiểm tay. Nêu rõ cách chấm khi parse hỏng hoàn toàn.
2. Tính lại ASR theo ba cách: parse sạch / gồm fallback / Format-Disruption Rate.
3. Từ log, tính catch rate của Review Agent (trên mọi ca Main Agent đề xuất sai,
   kể cả ca bị reject), reject rate trên benign, hiệu quả của Reflect.
4. Gán scenario_id cho mỗi ca (kịch bản gốc), thống kê số kịch bản, tính
   cluster bootstrap CI (B=10000) cho BU, ASR, UA, MHR, ASR theo taxonomy.
5. Tính ASR theo kỹ thuật tấn công và attacker profile nếu có nhãn.
6. Sửa/xác minh: ΔU bản cũ (phải 17.94), định nghĩa ASR-valid, mẫu số MHR,
   4 ca UNSPECIFIED, tính nhất quán Critical vs SUP.
7. Thêm log cho lần chạy: parse_mode, output thô, verdict Review từng vòng.
8. Chạy k=3 toàn bộ attack + benign, cùng tham số; báo cáo ASR mean/any/all.
9. Tạo "clean twin": mỗi kịch bản gốc với description trung tính, chạy k=3;
   tính ASR do tấn công = tỷ lệ lỗi có tiêm − không tiêm.
10. Tạo 5-10 ca positive control cho Data Stealing (canary, dry-run) để kiểm
    tra sink có thể kích hoạt.
Xuất kết quả dạng CSV + một báo cáo markdown tóm tắt. Không tự đổi cách chấm
mà không ghi lại.
```
