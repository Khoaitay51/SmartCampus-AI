# BÁO CÁO KẾT QUẢ ĐÁNH GIÁ PHÂN HỆ TẤN CÔNG (ATTACK BENCHMARK REPORT)

## 1. Các Chỉ Số Headline Cốt Lõi

| Chỉ Số Metric | Giá Trị Thực Nghiệm | Khoảng Tin Cậy 95% CI | Ý Nghĩa / Mục Tiêu |
| :--- | :---: | :---: | :--- |
| **Valid Rate** | **100.00%** (315/315) | — | Tỷ lệ chạy thành công không crash runtime |
| **ASR-valid (Headline)** | **12.98%** (34/262) | [9.44%, 17.59%] | **Tỷ lệ tấn công thành công trên các ca hợp lệ** |
| **ASR-all (Cận dưới)** | **12.67%** (38/300) | [9.37%, 16.91%] | Tỷ lệ tấn công trên toàn bộ 300 ca (coi invalid là defensed) |
| **Benign Baseline (BU)** | **93.00%** | — | Hiệu năng hữu ích trong môi trường sạch cố định |
| **Utility under Attack (UA)** | **82.06%** (215/262) | [76.96%, 86.23%] | Tỷ lệ giữ vững an toàn/bảo vệ khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích (ΔU)** | **+10.94%** | — | Mức độ suy giảm hiệu năng do tấn công gây ra (BU - UA) |
| **Missed Hazard Rate (MHR)** | **22.22%** (36/162) | [16.51%, 29.23%] | Tỷ lệ bỏ sót phản ứng khẩn cấp trong nguy hiểm |

---

## 2. Chi Tiết Phân Bổ Theo 4 Nhóm Tấn Công (Track A)

| Nhóm Tấn Công | Tên Đầy Đủ | Số Ca | ASR (%) | 95% CI | Ghi Chú Đánh Giá |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **DH-A** | Harm - Actuation (Tác động phần cứng) | 66 | **19.70%** | [11.89%, 30.84%] |  |
| **DH-S** | Harm - Security (Xâm phạm an ninh) | 36 | **5.56%** | [1.54%, 18.14%] |  |
| **SUP** | Safety Suppression (Triệt tiêu bảo vệ) | 60 | **31.67%** | [21.31%, 44.23%] |  |
| **DS** | Data Stealing (Trích xuất dữ liệu) | 100 | **0.00%** | [0.00%, 3.70%] | S1 Recon: 0.0% | S2 Exfil: 0.0% |

---

## 3. Khả Năng Chống Chịu Sự Cố Hệ Thống (Track B Robustness)

- **Tổng tỷ lệ vượt qua (Overall Robustness Pass Rate):** **56.25%** (9/16) — 95% CI: [33.18%, 76.90%]

| Sub-track | Mã Nhóm | Số Ca | Tỷ Lệ Đạt (Pass Rate) | 95% CI |
| :---: | :--- | :---: | :---: | :---: |
| **SER** | Stale Event Replay (Phát lại sự kiện quá hạn) | 4 | **25.00%** | [4.56%, 69.94%] |
| **CDR** | Cross-Device Conflict (Xung đột cảm biến) | 4 | **75.00%** | [30.06%, 95.44%] |
| **WTR** | Wrong Tool Suggestion (Lừa chọn sai tool) | 4 | **75.00%** | [30.06%, 95.44%] |
| **PMR** | Parameter Manipulation (Thao túng tham số) | 4 | **50.00%** | [15.00%, 85.00%] |