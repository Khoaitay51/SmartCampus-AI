# Báo cáo tổng hợp hiện trạng: SmartCampus Agent Security (advanced attack v3 làm trọng tâm)

Ngày rà soát: 2026-11-02. Nguồn số liệu: `runs/advanced_benchmark_full/raw_runs.jsonl` và `eval_advanced_attack.json` (285 lượt, k=1, Gemini 3.5 Flash Lite, đều `run_status = OK`), `benign_test/results/with_conf_reflect`, `analysis/out_advanced/stage_summary.md`, `analysis/out_clean_twin/`. Các benchmark trước (v1, attack v2) chỉ làm bối cảnh quá trình.
Cách đọc: **[Đã kiểm]** = tôi tính lại từ log. **[Bạn kiểm]** = bạn xác nhận thủ công. **[Chưa kiểm]** = chưa có bằng chứng.

---

## 1. Kết luận một đoạn

Số liệu lõi vững: ASR 22.05% (56/254) tái tính khớp evaluator, 0 ca lệch. Sau khi bạn kiểm tay 42 ca fallback, parser không còn là điểm yếu. **C1 và C3 đủ điều kiện đưa vào paper (kèm vài sửa câu chữ). C2 có bằng chứng mạnh nhưng còn thiếu clean twin đủ k và một bước kiểm novelty. C4 chưa có dữ liệu, hoãn.** Rủi ro lớn nhất nằm ở thống kê (chỉ 5 kịch bản gốc, 60 profile, k=1, một model), không phải ở cách chấm.

---

## 2. Cấu trúc thực của bộ dữ liệu (cần ghi vào paper)

| Thành phần | Số lượng | Ghi chú |
|---|---|---|
| Kịch bản gốc (U1..U5: cùng cảm biến, SOP, context) | **5** | Đơn vị độc lập thật sự |
| Attacker profile | **60** (DH-A 22, SUP 22, DH-S 10, DS 6) | 27/60 profile có ít nhất 1 ca thành công; profile cao nhất 5/5 |
| Ca tấn công hợp lệ (tích kịch bản × profile, đã lọc ca vô nghĩa) | 254 | DH-A 100, SUP 88, DH-S 36, DS 30 |
| Ca có hiểm họa thật (`requires_protective_action`) | 216 | 38 ca ở U5 (phòng bình thường) |
| Benign control cùng harness (clean twin) | 15 | 5 kịch bản × 3 mô tả trung tính |
| Track B | 16 | Phụ, 10/16 đạt |
| Benign độc lập (benign_test) | 100 | Sự kiện khác, 60 ca không cần hành động, 40 ca cần hành động |

ASR theo kịch bản gốc: U1 23.3% (14/60), U2 23.9% (11/46), U3 32.1% (17/53), U4 14.0% (8/57), U5 15.8% (6/38).

Hệ quả: 254 ca **không độc lập**. Wilson CI trên n=254 quá hẹp; cluster bootstrap với 5 cụm cũng không đáng tin. Bảng theo kịch bản và theo profile là cách trình bày trung thực.

---

## 3. Số liệu chính (đã tái tính)

| Chỉ số | Giá trị | Trạng thái |
|---|---|---|
| ASR (gồm fallback) | 22.05% (56/254) | [Đã kiểm] |
| ASR parse sạch | 18.87% (40/212) | [Đã kiểm] |
| ASR trong nhóm fallback | 38.10% (16/42) | [Đã kiểm]; 16 ca thành công đã được bạn xác nhận là thật |
| ASR theo taxonomy | SUP 36.36% (32/88), DH-A 22.00% (22/100), DH-S 5.56% (2/36), DS 0% (0/30) | [Đã kiểm] |
| Mức nghiêm trọng | Critical 12.60% (32), Major 7.87% (20), Unspecified 1.57% (4) | [Đã kiểm]. Gộp 4 ca vào Major thành 9.45% (24) là đề xuất, chưa là quy ước chính thức |
| MHR | **25.46% (55/216)**: SUP 32/88, DH-A 18/78, DH-S 4/26, DS 1/24 | [Đã kiểm]. Con số 24.11% (54/224) là bản cũ |
| UA | 75.98% (193/254) | [Đã kiểm] |
| ΔU | 17.02 điểm nếu lấy BU = 93% (benign_test); 24.0 điểm nếu lấy clean twin cùng harness (15/15) | Cần chọn một mốc |
| Clean twin: "thành công" khi không tiêm | 0/254 ghép cặp (15 lượt gốc, 5 kịch bản; 12/12 ca có hiểm họa hành động đúng, 3/3 ca U5 đúng khi không làm gì) | [Đã kiểm], k=1 |
| Omission tự nhiên (benign_test) | 4/40 = 10% | [Đã kiểm] |
| Format-Disruption Rate | 16.54% (42/254) so với tự nhiên 11/100 | Chênh lệch **không có ý nghĩa** (Fisher p ≈ 0.25) |
| Review catch rate | Không có | [Chưa kiểm]: log không ghi verdict Review |

Persuasion bị lẫn với taxonomy nên không đưa bảng ASR-theo-persuasion như kết quả độc lập. Ví dụ `urgency` là 54/65 ca DH-A; `technical_notice` là 28/42 ca SUP.

---

## 4. Đánh giá từng đóng góp

### C1. Bộ benchmark (254 tấn công + 100 benign, nhãn từ SOP + cảm biến tại T0): **Ổn, cần ghi giới hạn**
Đã đủ:
- Nhãn xác định, không dùng LLM-as-judge; stage_labeler tái tính khớp evaluator.
- Có benign cùng harness (15) và benign độc lập (100).

Cần làm khi viết:
- Nêu rõ cấu trúc 5 kịch bản × 60 profile (mục 2). Không gọi là "254 kịch bản".
- Ghi rõ "nhãn suy ra từ trạng thái cảm biến trong gói sự kiện tại T0 và SOP", không phải "đọc từ TimescaleDB".
- Bộ attack v3 được thiết kế sau khi xem kết quả v2 trên cùng model, nên ASR có thể cao hơn mức tổng quát (in-sample). Ghi vào Limitations.
- Một model, k=1.

### C2. Omission là lớp tấn công riêng, SUP ASR cao: **Chưa đủ, nhưng gần**
Đã có:
- SUP 36.4% (32/88) ở 4 kịch bản có hiểm họa; 31/32 ca là model chủ động `skip`, không do parser.
- Clean twin: 0/88 omission khi không tiêm; omission tự nhiên 10% ở benign_test. Tấn công làm omission từ ~0–10% lên 36%.
- Stage funnel: 26 ca `omission_adopted_claim` (Agent trích dẫn lý do của kẻ tấn công) so với 2 ca `omission_unreferenced`.

Còn thiếu:
1. Clean twin mới k=1, 15 lượt. Cần k=3 và nhánh claim-only (xem `PLAN_CLEAN_TWIN_C2.md`).
2. "SUP cao nhất" chưa kiểm định: trong U1..U4, DH-A khoảng 21.8% (17/78) so với SUP 36.4%; CI chồng nhau một phần, và hai nhóm dùng profile khác nhau. Nên nói "SUP cao hơn DH-A trong quan sát" cho tới khi có kiểm định hoặc k=3.
3. Kiểm tra novelty chưa làm (R1 Evil-AI Bench, R2 PromptShield-Home, R4 tiền lệ SUP). Nếu có bài đã làm đúng việc này thì phải hạ C2.
4. Giới hạn: chỉ 4 kịch bản có hiểm họa; SUP không áp dụng ở U5.

### C3. Audit harness (parser fallback, ASR dạng khoảng, FDR): **Ổn sau khi bạn kiểm tay, cần chỉnh một câu**
Đã có:
- Bạn kiểm tay 42/42: parser khớp ý định, ASR thành công là thật. Đây là bằng chứng chính, cần lưu thành file (xem mục 6).
- SUP: 0/32 ca do parser hỏng.
- ASR báo dạng khoảng: 18.87% → 22.05%.

Cần chỉnh:
- **Bỏ câu "lỗi cú pháp do IPI"** ở FDR. Dữ liệu cho thấy 16.5% so với 11% tự nhiên, p ≈ 0.25. Nói đúng: FDR là chỉ số rủi ro harness, và vì parser khớp ý định nên không làm lệch ASR.
- Câu "ASR cao gấp đôi ở nhóm fallback" giữ ở dạng tương quan (38.1% so với 18.9%), chưa kiểm soát confounder.
- Giá trị đóng góp của C3 là phương pháp báo cáo (ASR kèm FDR, kèm audit), không phải phát hiện về model.

### C4. Review Agent đồng nhiễm: **Hoãn (đúng như bạn quyết)**
- Log không có verdict Review; con số "catch rate 0%" hiện chỉ là câu in cố định trong script, không phải kết quả đo.
- Cần gỡ khỏi docx mọi chỗ khẳng định "xác nhận thực nghiệm co-vulnerability" cho tới khi có log.

---

## 5. Danh sách cần đồng bộ trong docx và báo cáo Phase 1

| # | Vấn đề | Cách xử lý đề xuất |
|---|---|---|
| 1 | MHR: giải thích 224 so với 216 ("thiếu 1 ca DS") sai. 224 = 254 − 30 DS; 216 = loại 32 ca U5 phi-DS, thêm 24 ca DS có hiểm họa | Chốt 55/216, sửa lời giải thích |
| 2 | ΔU dùng BU từ benchmark khác phân bố | Nêu cả hai mốc; mốc chính là clean twin cùng harness |
| 3 | FDR "do IPI" | Bỏ nhân quả; ghi FDR tự nhiên 11/100 |
| 4 | "Kiểm toán 42/42" | Ghi là kiểm tay thủ công và lưu bảng |
| 5 | Catch rate 0%, "xác nhận co-vulnerability" | Gỡ khỏi phần kết quả, chuyển Limitations/future work |
| 6 | MODE_PERMISSIONS mâu thuẫn giữa các báo cáo | Bỏ phần này theo plan phương pháp luận |
| 7 | Cluster bootstrap 5 cụm (FDR [3.7, 30.5], ΔU [9.5, 24.3]) | Bỏ hoặc ghi "5 cụm, chỉ tham khảo"; dùng bảng theo kịch bản |
| 8 | Bảng persuasion lẫn taxonomy | Chuyển thành bảng phụ kèm ghi chú confounder |
| 9 | Related work: AgentSentry "ASR về 0%", Evil-AI "IEEE 2024", Firewalls | Kiểm tra lại (R7) |
| 10 | Plan cũ ghi 278 ca, ΔU 10.94, ASR 12.98%; docx Phase 3 gọi kết quả là "chứng minh", "minh chứng xuất sắc" | Thống nhất 285 ca, ΔU như mục 3; bỏ ngôn từ tuyệt đối |
| 11 | Phần 3-tier defense trong ADVANCED_ATTACK_REPORT | Giữ như hướng tương lai, không như kết quả |

---

## 6. Việc cần làm theo thứ tự ưu tiên

1. **Lưu bằng chứng kiểm tay 42 ca** (bảng id, lý do fallback, khớp/không, ghi chú) vào `methodology_review/t1_manual_audit.csv`. Đây là nền cho C3.
2. **Đồng bộ 11 điểm ở mục 5** vào một bản số liệu duy nhất.
3. **Clean twin nhánh N (k=3)** rồi nhánh P (claim-only). Cần bật Gateway :8000 và DB :5433.
4. **R1, R4, R2**: kiểm tra novelty của omission. Đây là việc quyết định C2 giữ hay hạ.
5. **R7** (kiểm số liệu và trích dẫn) và R9 (viết).
6. Sau cùng, tùy thời gian: k=3 toàn bộ (T8), positive control cho DS (T10), log verdict Review cho C4.

## 7. Giới hạn cần nêu trong paper
Một model, k=1, 5 kịch bản gốc, 60 profile, attack v3 điều chỉnh sau khi xem v2 trên cùng model, DS = 0% chưa có positive control (nên ghi "chưa kích hoạt được trong cấu hình hiện tại" thay vì "0% rò rỉ").
