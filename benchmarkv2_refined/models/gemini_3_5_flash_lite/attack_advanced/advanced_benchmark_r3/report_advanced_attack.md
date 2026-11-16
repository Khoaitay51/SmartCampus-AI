# BÁO CÁO KẾT QUẢ THỰC NGHIỆM PHASE 3: ADVANCED ATTACK BENCHMARK

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa Đánh Giá |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** | — | Độ ổn định runtime trên môi trường Live |
| **ASR-valid (Headline)** | **31.50%** (80/254) | [26.10%, 37.45%] | **Tỷ lệ tấn công thành công trên 254 ca Track A** |
| **Benign Baseline (BU)** | **93.00%** | — | Mốc sạch cố định từ Benign Benchmark |
| **Utility under Attack (UA)** | **59.06%** (150/254) | [52.92%, 64.92%] | Tỷ lệ duy trì bảo vệ/an toàn khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **+33.94%** | — | Mức suy giảm an toàn thực tế (BU - UA) |
| **Missed Hazard Rate (MHR)** | **40.62%** (91/224) | [34.40%, 47.16%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A Nâng Cao)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động thiết bị) | 100 | **30.00%** | [21.89%, 39.58%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 36 | **5.56%** | [1.54%, 18.14%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 88 | **54.55%** | [44.17%, 64.54%] |  |
| **DS** | Data Stealing (Trojan Audit Exfil) | 30 | **0.00%** | [0.00%, 11.35%] | S1 Recon: 3.3% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua:** **68.75%** (11/16) — 95% CI: [44.40%, 85.84%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 4 | **25.00%** | [4.56%, 69.94%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 4 | **100.00%** | [51.01%, 100.00%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 4 | **100.00%** | [51.01%, 100.00%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 4 | **50.00%** | [15.00%, 85.00%] |