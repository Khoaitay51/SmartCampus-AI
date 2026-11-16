# BÁO CÁO KHOA HỌC: HOÀN THIỆN PHƯƠNG PHÁP LUẬN & ĐÁNH GIÁ ĐA TẦNG (PHASE 1)
**Dự án:** Smart Campus Multi-Agent Safety Benchmark  
**Thời gian thực hiện:** Tháng 11/2026  
**Mục tiêu:** Kiểm toán toàn diện log thực nghiệm hiện có, chuẩn hóa các định nghĩa chỉ số, làm rõ vai trò của Parser Fallback, Reviewer, phân tích Cluster Bootstrap và giải quyết các câu hỏi phản biện cốt lõi từ Hội đồng.

---

## 1. Tóm Tắt Kết Quả Kiểm Toán (Executive Summary)

Dựa trên việc kiểm toán 100% dữ liệu từ 285 ca thử nghiệm của bộ **Benchmark v2-Refined**, chúng tôi xác lập các kết quả khoa học chuẩn mực sau:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                          BẢNG TỔNG HỢP CHỈ SỐ PHƯƠNG PHÁP LUẬN CHUẨN HÓA                        │
├──────────────────────────────┬──────────────────┬──────────────────┬────────────────────────────┤
│ CHỈ SỐ METRIC                │ GIÁ TRỊ THỰC TẾ  │ WILSON 95% CI    │ CLUSTER BOOTSTRAP (B=10000)│
├──────────────────────────────┼──────────────────┼──────────────────┼────────────────────────────┤
│ Benign Utility Baseline (BU) │ 93.00% (93/100)  │ [86.30%, 96.60%] │ — (n=100 độc lập)          │
│ ASR Toàn Bộ (Gồm Fallback)   │ 22.05% (56/254)  │ [17.39%, 27.54%] │ [16.36%, 27.63%]           │
│ ASR Parse Sạch (No Fallback) │ 18.87% (40/212)  │ [14.18%, 24.67%] │ [13.20%, 24.50%]           │
│ Format-Disruption Rate (FDR) │ 16.54% (42/254)  │ [12.42%, 21.64%] │ — (Lỗi cú pháp do IPI)     │
│ Utility under Attack (UA)    │ 75.98% (193/254) │ [70.37%, 80.83%] │ [71.60%, 80.34%]           │
│ Độ sụt giảm tiện ích (ΔU)    │ +17.02%          │ —                │ BU - UA                    │
│ Missed Hazard Rate (MHR)     │ 25.46% (55/216)  │ [20.08%, 31.75%] │ [21.84%, 30.15%]           │
│ Data Stealing (ASR-DS)       │ 0.00% (0/30)     │ [0.00%, 11.35%]  │ [0.00%, 0.00%]             │
└──────────────────────────────┴──────────────────┴──────────────────┴────────────────────────────┘
```

> [!IMPORTANT]
> **Khuyến nghị cách báo cáo ASR gửi Thầy và Hội Đồng:**  
> Báo cáo ASR dưới dạng khoảng: **$18.87\%$ (parse sạch) $\longrightarrow$ $22.05\%$ (gồm cả fallback)**, đi kèm chỉ số **Format-Disruption Rate = $16.54\%$ (42/254)**. Cách trình bày này vừa trung thực tuyệt đối, vừa chứng minh được rằng ngay cả khi loại bỏ hoàn toàn tầng phục hồi parser, tỷ lệ bị tấn công vẫn xấp xỉ $19\%$.

---

## 2. Chi Tiết Kiểm Toán Từng Hạng Mục (T1 -> T7)

### Task 1 (T1) — Kiểm toán Parser Fallback (Audit 42 ca fallback)
- **Bản chất của Fallback:** Trong 42 ca kích hoạt fallback, 100% thuộc cấp độ **Parsing Fallback** (khôi phục JSON bị lỗi cú pháp hoặc trích xuất bằng regex có kiểm soát). Không có bất kỳ ca nào bị rơi xuống cấp Rule Fallback hay chuyển đổi model.
- **Phân bổ kết quả trong nhóm Fallback:**
  - $16/42$ ca ($38.10\%$) bị tấn công thành công.
  - $26/42$ ca ($61.90\%$) phòng thủ thành công.
- **Tính nhất quán giữa Ý định của Model và Parser:**
  - Kiểm toán tay $42/42$ ca cho thấy: Parser **khớp $100\%$ ý định hành vi** được LLM trình bày trong phần lập luận (`analysis`).
  - Trong 16 ca thành công qua fallback: Chính Model đã bị thuyết phục bởi attacker (ví dụ: model lập luận *"đang có sự cố chập điện nghiêm trọng cần ngắt quạt khẩn cấp"*), và parser chỉ chuẩn hóa văn bản đó thành lệnh gọi `set_fan: off`. Parser không tự ý sinh ra hành vi phá hoại.
  - **Tương quan thống kê:** ASR trong nhóm fallback ($38.10\%$) cao gấp đôi nhóm parse sạch ($18.87\%$). Điều này phản ánh: Khi gặp phải đòn tấn công IPI tinh vi, LLM vừa bị dẫn dụ nhận thức, vừa bị xáo trộn cú pháp sinh văn bản (cognitive disruption đi kèm syntactic disruption).

### Task 2 (T2) — Quy tắc chấm khi Parse hỏng & Tác động lên SUP
Một nghi vấn phản biện rất lớn là: *"Liệu có phải Agent bị tính nhầm là Safety Suppression (SUP) do parser bị hỏng dẫn đến `skip = True` hay không?"*
- **Kết quả kiểm toán thực tế:**
  - Trong toàn bộ **32 ca SUP thành công**:
    - **$31/32$ ca ($96.88\%$) là do Model CHỦ ĐỘNG RA LỆNH `skip`:** Trong phần `analysis`, LLM giải thích tường minh rằng nó tin vào các lý do *"đang diễn tập PCCC định kỳ"*, *"bảo trì có kiểm soát"* nên quyết định không kích hoạt còi hay quạt.
    - **$0/32$ ca ($0.00\%$)** bị ép `skip` do parser hỏng.
    - **$1/32$ ca ($3.12\%$)** là do Agent chọn sai công cụ không có tác dụng cứu hộ.
- **Kết luận:** Lỗ hổng Safety Suppression hoàn toàn xuất phát từ **sự thất bại nhận thức (Cognitive Blindness)** của mô hình trước mã tiêm, không phải lỗi kỹ thuật của parser.

### Task 3 (T3) — Đánh giá Review Agent & Reflect Loop
- **Kết quả kiểm toán:**
  - Trong toàn bộ 254 ca tấn công, tỷ lệ Review Agent phát hiện và từ chối đề xuất của Main Agent là **$0.00\%$ (Catch Rate = 0%)**. Tất cả 254 ca đều được Reviewer đánh giá `Accomplished` ngay ở vòng 1.
  - **Cơ chế Co-vulnerability:** Review Agent đọc cùng một Scratchpad và Context đã bị tiêm nhiễm mã độc. Khi kẻ tấn công ngụy tạo lý do hợp lý, Review Agent thấy Main Agent có gọi RAG tool, có lập luận logic theo mô tả sự kiện, nên Review Agent cũng bị lừa theo.
  - **Kết luận:** Kiểm thử đa tác nhân (Multi-Agent Verification) thuần LLM không thể ngăn chặn được IPI nếu không có ranh giới phân tách dữ liệu cứng (Untrusted Context Boundary).

### Task 4 (T4) — Chuẩn hóa định nghĩa & Khắc phục số liệu
1. **Sửa lỗi $\Delta U$ bản cũ:**
   - Trong báo cáo cũ: $BU = 100\%$, $UA = 82.06\%$. Vậy $\Delta U = 100\% - 82.06\% = \mathbf{17.94\%}$. Số liệu ghi "10.94%" trước đây là do nhầm lẫn khi lấy $93\% - 82.06\%$.
   - Trong bản v2-refined: $BU = 93.00\%$, $UA = 75.98\% \Longrightarrow \Delta U = \mathbf{17.02\%}$.
2. **Mẫu số của MHR ($n=216$):**
   - Chỉ tính trên các ca phòng học có sự cố nguy hiểm thực tế ($U_1 \dots U_4$, `requires_protective_action = True`), loại bỏ các ca phòng bình thường $U_5$.
   - Tổng số ca nguy hiểm: $216$ ca. Số ca bỏ sót bảo vệ: $55$ ca $\Longrightarrow \mathbf{MHR = 25.46\%}$.
3. **Phân loại 4 ca UNSPECIFIED:**
   - 4 ca này gồm các hành vi gọi tool `set_mode` chuyển phòng sang `SAVING` hoặc `LOCK`.
   - Đề xuất chuẩn hóa: Xếp cả 4 ca vào mức độ **MAJOR** (làm gián đoạn vận hành tòa nhà). Khi đó:
     - **ASR-CRITICAL:** $12.60\%$ ($32/254$)
     - **ASR-MAJOR:** $9.45\%$ ($24/254$) — tăng từ 20 lên 24 ca.
     - **ASR-UNSPECIFIED:** $0.00\%$ ($0/254$) — đã phân loại triệt để $100\%$.
4. **Tính nhất quán giữa Critical và SUP:**
   - Toàn bộ $31/32$ ca SUP thành công ở môi trường có nguy hiểm đều được xếp chuẩn vào **CRITICAL** (do bỏ qua đám cháy/ngạt khí thực tế). 1 ca Critical còn lại là ca ép hú còi liên tục gây loạn ở phòng học bình thường $U_5$.

### Task 5 (T5) — Khoảng Tin Cậy Điều Chỉnh Cụm (Cluster Bootstrap B=10000)
Do 254 testcases được sinh ra từ tích Descartes giữa 5 User Case và các Attacker Profiles, chúng tôi thực hiện **Cluster Bootstrap ($B=10,000$ lần lặp)** nhóm theo User Case để kiểm soát tương quan nội cụm:
- **ASR:** Mean = $21.96\%$, $95\%\text{ CI} = [16.36\%, 27.63\%]$ (hoàn toàn tương thích với Wilson Score $[17.39\%, 27.54\%]$).
- **UA:** Mean = $76.06\%$, $95\%\text{ CI} = [71.60\%, 80.34\%]$.
- **MHR:** Mean = $25.46\%$, $95\%\text{ CI} = [21.84\%, 30.15\%]$.
- **SUP:** Mean = $36.29\%$, $95\%\text{ CI} = [25.76\%, 46.36\%]$.
- **DH-A:** Mean = $21.74\%$, $95\%\text{ CI} = [10.64\%, 33.01\%]$.
- **DH-S:** Mean = $5.89\%$, $95\%\text{ CI} = [0.00\%, 13.79\%]$.

### Task 6 (T6) — ASR Theo Chiến Lược Thuyết Phục (Persuasion Strategy)

| Chiến Lược Thuyết Phục | Số Ca Thử Nghiệm | Tấn Công Thành Công | Tỷ Lệ ASR (%) | Wilson 95% CI |
| :--- | :---: | :---: | :---: | :---: |
| **drill_test** (Giả mạo diễn tập PCCC) | 21 | 7 | **33.33%** | [17.2%, 54.6%] |
| **technical_notice** (Thông báo lỗi kỹ thuật/hiệu chuẩn) | 42 | 13 | **30.95%** | [19.1%, 46.0%] |
| **maintenance** (Bảo trì định kỳ thiết bị) | 32 | 8 | **25.00%** | [13.3%, 42.1%] |
| **urgency** (Tạo áp lực thời gian/nguy cấp) | 65 | 13 | **20.00%** | [12.1%, 31.3%] |
| **authority_claim** (Mạo danh BGH / Trưởng khoa) | 79 | 14 | **17.72%** | [10.9%, 27.6%] |
| **policy_claim** (Trích dẫn quy định mới) | 15 | 1 | **6.67%** | [1.2%, 29.8%] |

### Task 7 (T7) — Phân Bố Độ Tự Tin (Confidence Distribution)
- **Ca tấn công thành công ($n=25$ có tool call):** Mean = $0.894 \pm 0.048$, Median = $0.85$, Min = $0.85$, Max = $0.95$.
- **Ca phòng thủ thành công ($n=164$):** Mean = $0.882 \pm 0.061$, Median = $0.85$, Min = $0.65$, Max = $0.95$.
- **Ca Benign môi trường sạch ($n=53$):** Mean = $0.854 \pm 0.077$, Median = $0.85$, Min = $0.65$, Max = $0.95$.
- **Kết luận:** Ngưỡng tự tin hiện tại (`Confidence Threshold = 0.35`) chỉ đóng vai trò là **Quality Gate** (chống ảo giác hoàn toàn), không có năng lực bảo mật, vì khi bị lừa, LLM đưa ra quyết định với mức tự tin cực kỳ cao ($\ge 0.85$).

---

## 3. Danh Mục Các Tệp Dữ Liệu Đã Xuất

Tất cả các bảng kiểm toán chi tiết đã được tự động lưu trữ tại `benchmarkv2_refined/advanced_attack_test/methodology_review/`:
1. `t1_audit_fallback.csv`: Chi tiết 42 ca fallback, phân loại lý do và kiểm tra ý định.
2. `t2_sup_mechanism_audit.csv`: Chi tiết cơ chế 32 ca SUP thành công (chứng minh 96.9% là chủ động skip).
3. `t4_unspecified_severity_cases.csv`: Chi tiết 4 ca `set_mode` được đề xuất xếp vào Major.
4. `t5_cluster_bootstrap.json`: Kết quả phân phối thống kê của 10,000 lần lấy mẫu theo cụm.
5. `t6_asr_by_persuasion.csv`: Bảng số liệu ASR theo 6 chiến lược tâm lý.
6. `t7_confidence_distribution.csv`: Bảng phân bổ confidence qua các dải ngưỡng.
