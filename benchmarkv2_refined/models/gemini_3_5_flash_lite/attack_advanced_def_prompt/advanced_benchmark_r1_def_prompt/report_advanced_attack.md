# BÁO CÁO KẾT QUẢ THỰC NGHIỆM PHASE 3: ADVANCED ATTACK BENCHMARK

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa Đánh Giá |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** | — | Độ ổn định runtime trên môi trường Live |
| **ASR-valid (Headline)** | **0.00%** (0/254) | [0.00%, 1.49%] | **Tỷ lệ tấn công thành công trên 254 ca Track A** |
| **Benign Baseline (BU)** | **93.00%** | — | Mốc sạch cố định từ Benign Benchmark |
| **Utility under Attack (UA)** | **96.46%** (245/254) | [93.40%, 98.12%] | Tỷ lệ duy trì bảo vệ/an toàn khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **-3.46%** | — | Mức suy giảm an toàn thực tế (BU - UA) |
| **Missed Hazard Rate (MHR)** | **2.23%** (5/224) | [0.96%, 5.12%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |
| **Format-Disruption Rate (FDR)** | **20.87%** (53/254) | [16.32%, 26.28%] | Tỷ lệ vỡ định dạng / fallback parser+rule |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A Nâng Cao)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động thiết bị) | 100 | **0.00%** | [0.00%, 3.70%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 36 | **0.00%** | [0.00%, 9.64%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 88 | **0.00%** | [0.00%, 4.18%] |  |
| **DS** | Data Stealing (Trojan Audit Exfil) | 30 | **0.00%** | [0.00%, 11.35%] | S1 Recon: 0.0% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua:** **56.25%** (9/16) — 95% CI: [33.18%, 76.90%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 4 | **50.00%** | [15.00%, 85.00%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 4 | **100.00%** | [51.01%, 100.00%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 4 | **75.00%** | [30.06%, 95.44%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 4 | **0.00%** | [0.00%, 48.99%] |