# BÁO CÁO KẾT QUẢ THỰC NGHIỆM PHASE 3: ADVANCED ATTACK BENCHMARK

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa Đánh Giá |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** | — | Độ ổn định runtime trên môi trường Live |
| **ASR-valid (Headline)** | **12.20%** (31/254) | [8.73%, 16.80%] | **Tỷ lệ tấn công thành công trên 254 ca Track A** |
| **Benign Baseline (BU)** | **92.00%** | — | Mốc sạch cố định từ Benign Benchmark |
| **Utility under Attack (UA)** | **81.89%** (208/254) | [76.69%, 86.14%] | Tỷ lệ duy trì bảo vệ/an toàn khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **+10.11%** | — | Mức suy giảm an toàn thực tế (BU - UA) |
| **Missed Hazard Rate (MHR)** | **18.75%** (42/224) | [14.18%, 24.37%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |
| **Format-Disruption Rate (FDR)** | **14.17%** (36/254) | [10.42%, 19.00%] | Tỷ lệ vỡ định dạng / fallback parser+rule |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A Nâng Cao)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động thiết bị) | 100 | **5.00%** | [2.15%, 11.18%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 36 | **2.78%** | [0.49%, 14.17%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 88 | **28.41%** | [20.04%, 38.58%] |  |
| **DS** | Data Stealing (Trojan Audit Exfil) | 30 | **0.00%** | [0.00%, 11.35%] | S1 Recon: 0.0% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua:** **75.00%** (12/16) — 95% CI: [50.50%, 89.82%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 4 | **75.00%** | [30.06%, 95.44%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 4 | **100.00%** | [51.01%, 100.00%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 4 | **75.00%** | [30.06%, 95.44%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 4 | **50.00%** | [15.00%, 85.00%] |