# BÁO CÁO KẾT QUẢ THỰC NGHIỆM PHASE 3: ADVANCED ATTACK BENCHMARK

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa Đánh Giá |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** | — | Độ ổn định runtime trên môi trường Live |
| **ASR-valid (Headline)** | **3.94%** (10/254) | [2.15%, 7.09%] | **Tỷ lệ tấn công thành công trên 254 ca Track A** |
| **Benign Baseline (BU)** | **86.00%** | — | Mốc sạch cố định từ Benign Benchmark |
| **Utility under Attack (UA)** | **91.34%** (232/254) | [87.23%, 94.21%] | Tỷ lệ duy trì bảo vệ/an toàn khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **-5.34%** | — | Mức suy giảm an toàn thực tế (BU - UA) |
| **Missed Hazard Rate (MHR)** | **8.93%** (20/224) | [5.85%, 13.39%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |
| **Format-Disruption Rate (FDR)** | **8.27%** (21/254) | [5.47%, 12.31%] | Tỷ lệ vỡ định dạng / fallback parser+rule |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A Nâng Cao)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động thiết bị) | 100 | **4.00%** | [1.57%, 9.84%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 36 | **0.00%** | [0.00%, 9.64%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 88 | **6.82%** | [3.16%, 14.09%] |  |
| **DS** | Data Stealing (Trojan Audit Exfil) | 30 | **0.00%** | [0.00%, 11.35%] | S1 Recon: 10.0% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua:** **68.75%** (11/16) — 95% CI: [44.40%, 85.84%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 4 | **75.00%** | [30.06%, 95.44%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 4 | **100.00%** | [51.01%, 100.00%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 4 | **75.00%** | [30.06%, 95.44%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 4 | **25.00%** | [4.56%, 69.94%] |