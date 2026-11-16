# BÁO CÁO KẾT QUẢ THỰC NGHIỆM PHASE 3: ADVANCED ATTACK BENCHMARK

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa Đánh Giá |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** | — | Độ ổn định runtime trên môi trường Live |
| **ASR-valid (Headline)** | **20.00%** (2/10) | [5.67%, 50.98%] | **Tỷ lệ tấn công thành công trên 254 ca Track A** |
| **Benign Baseline (BU)** | **93.00%** | — | Mốc sạch cố định từ Benign Benchmark |
| **Utility under Attack (UA)** | **70.00%** (7/10) | [39.68%, 89.22%] | Tỷ lệ duy trì bảo vệ/an toàn khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **+23.00%** | — | Mức suy giảm an toàn thực tế (BU - UA) |
| **Missed Hazard Rate (MHR)** | **30.00%** (3/10) | [10.78%, 60.32%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A Nâng Cao)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động thiết bị) | 10 | **20.00%** | [5.67%, 50.98%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 0 | **0.00%** | [0.00%, 0.00%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 0 | **0.00%** | [0.00%, 0.00%] |  |
| **DS** | Data Stealing (Trojan Audit Exfil) | 0 | **0.00%** | [0.00%, 0.00%] | S1 Recon: 0.0% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua:** **0.00%** (0/0) — 95% CI: [0.00%, 0.00%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 0 | **0.00%** | [0.00%, 0.00%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 0 | **0.00%** | [0.00%, 0.00%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 0 | **0.00%** | [0.00%, 0.00%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 0 | **0.00%** | [0.00%, 0.00%] |