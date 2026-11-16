# BÁO CÁO KẾT QUẢ ĐÁNH GIÁ PHÂN HỆ TẤN CÔNG (ATTACK BENCHMARK REPORT)

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa / Mục Tiêu |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** (10/10) | — | Tỷ lệ chạy thành công không crash runtime |
| **ASR-valid (Headline)** | **20.00%** (2/10) | [5.67%, 50.98%] | **Tỷ lệ tấn công thành công trên các ca hợp lệ** |
| **ASR-all (Cận dưới)** | **20.00%** (2/10) | [5.67%, 50.98%] | Tỷ lệ tấn công trên toàn bộ 300 ca (coi invalid là defensed) |
| **Benign Baseline (BU)** | **93.00%** | — | Hiệu năng hữu ích trong môi trường sạch cố định |
| **Utility under Attack (UA)** | **70.00%** (7/10) | [39.68%, 89.22%] | Tỷ lệ giữ vững an toàn/bảo vệ khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **+23.00%** | — | Mức độ suy giảm hiệu năng do tấn công gây ra (BU - UA) |
| **Missed Hazard Rate (MHR)** | **30.00%** (3/10) | [10.78%, 60.32%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động phần cứng) | 10 | **20.00%** | [5.67%, 50.98%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 0 | **0.00%** | [0.00%, 0.00%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 0 | **0.00%** | [0.00%, 0.00%] |  |
| **DS** | Data Stealing (Trích xuất dữ liệu) | 0 | **0.00%** | [0.00%, 0.00%] | S1 Recon: 0.0% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua (Overall Robustness Pass Rate):** **0.00%** (0/0) — 95% CI: [0.00%, 0.00%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 0 | **0.00%** | [0.00%, 0.00%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 0 | **0.00%** | [0.00%, 0.00%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 0 | **0.00%** | [0.00%, 0.00%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 0 | **0.00%** | [0.00%, 0.00%] |