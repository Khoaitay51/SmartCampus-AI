# BÁO CÁO KẾT QUẢ THỰC NGHIỆM PHASE 3: ADVANCED ATTACK BENCHMARK

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa Đánh Giá |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** | — | Độ ổn định runtime trên môi trường Live |
| **ASR-valid (Headline)** | **10.63%** (27/254) | [7.41%, 15.02%] | **Tỷ lệ tấn công thành công trên 254 ca Track A** |
| **Benign Baseline (BU)** | **85.00%** | — | Mốc sạch cố định từ Benign Benchmark |
| **Utility under Attack (UA)** | **72.83%** (185/254) | [67.05%, 77.93%] | Tỷ lệ duy trì bảo vệ/an toàn khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **+12.17%** | — | Mức suy giảm an toàn thực tế (BU - UA) |
| **Missed Hazard Rate (MHR)** | **27.23%** (61/224) | [21.82%, 33.41%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |
| **Format-Disruption Rate (FDR)** | **3.54%** (9/254) | [1.88%, 6.60%] | Tỷ lệ vỡ định dạng / fallback parser+rule |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A Nâng Cao)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động thiết bị) | 100 | **3.00%** | [1.03%, 8.45%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 36 | **0.00%** | [0.00%, 9.64%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 88 | **27.27%** | [19.07%, 37.38%] |  |
| **DS** | Data Stealing (Trojan Audit Exfil) | 30 | **0.00%** | [0.00%, 11.35%] | S1 Recon: 6.7% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua:** **31.25%** (5/16) — 95% CI: [14.16%, 55.60%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 4 | **50.00%** | [15.00%, 85.00%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 4 | **25.00%** | [4.56%, 69.94%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 4 | **50.00%** | [15.00%, 85.00%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 4 | **0.00%** | [0.00%, 48.99%] |