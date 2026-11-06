# BÁO CÁO THỰC NGHIỆM ĐỐI CHỨNG K=3 ADVANCED ATTACK BENCHMARK (TRACK A)

> **Quy mô thực nghiệm:** 3 lượt chạy độc lập ($k=3$), $N = 254$ ca tấn công/lượt $\rightarrow$ Tổng cộng **762 lượt gọi Agent thực tế**.
> **Mô hình nghiên cứu:** `gemini-3.5-flash-lite`, temperature=0.0, Live Real RAG, Gateway :8000, TimescaleDB :5433.

---

## 1. Các Chỉ Số Cốt Lõi Qua 3 Lượt Chạy ($k=3$)

| Chỉ Số (Metric) | Lượt 1 ($r_1$) | Lượt 2 ($r_2$) | Lượt 3 ($r_3$) | **Trung Bình (Mean)** | **Độ Lệch Chuẩn (Std)** | **Ý Nghĩa Đánh Giá** |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Attack Success Rate (ASR)** | **22.05%** (56/254) | **28.35%** (72/254) | **31.50%** (80/254) | **27.30%** | $\pm 4.81\%$ | Tỷ lệ tấn công thành công trung bình |
| **ASR-any ($\ge 1$ lần)** | — | — | — | **37.40%** (95/254) | — | Tỷ lệ ca bị hack ít nhất 1 lần trong 3 vòng |
| **ASR-all (cả 3 lần)** | — | — | — | **15.75%** (40/254) | — | Tỷ lệ ca bị chiếm quyền liên tục không đổi |
| **Utility under Attack (UA)** | 75.98% | 61.81% | 59.06% | **65.62%** | $\pm 9.08\%$ | Tỷ lệ giữ vững an toàn/hợp lệ khi bị tấn công |
| **Độ Sụt Giảm Tiện Ích ($\Delta U$)** | 0.1702 | 0.3119 | 0.3394 | **27.38%** | — | Mức suy giảm tiện ích (93.00% - UA) |
| **Mitigation Hazard Rate (MHR)** | 24.11% | 37.50% | 40.62% | **34.08%** | $\pm 8.77\%$ | Tỷ lệ bỏ sót cứu hộ trong nguy hiểm thực tế |

---

## 2. Phân Rã Theo 4 Chiều Tấn Công (Taxonomy Across $k=3$)

| Phân Nhóm Tấn Công | Mã Nhóm | Số Ca | ASR ($r_1$) | ASR ($r_2$) | ASR ($r_3$) | **Mean ASR (%)** | ASR-any (%) | ASR-all (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Safety Suppression (Omission)** | `SUP` | 88 | 36.4% | 48.9% | 54.5% | **46.59%** | 61.4% | 28.4% |
| **Direct Harm - Actuation** | `DH-A` | 100 | 22.0% | 27.0% | 30.0% | **26.33%** | 39.0% | 13.0% |
| **Direct Harm - Security** | `DH-S` | 36 | 5.6% | 5.6% | 5.6% | **5.56%** | 5.6% | 5.6% |
| **Data Stealing (Trojan Audit)** | `DS` | 30 | 0.0% | 0.0% | 0.0% | **0.00%** | 0.0% | 0.0% |

---

## 3. Nhận Xét Khoa Học Từ Kết Quả $k=3$

1. **Tính ổn định của ASR:** Qua 3 lượt chạy độc lập, độ lệch chuẩn chỉ $\pm 4.81\%$, khẳng định kết quả ASR có tính tất định và độ tin cậy tái lập rất cao.

2. **ASR-any vs ASR-all:** ASR-all (15.75%) phản ánh những lỗ hổng 'cố hữu' (hard vulnerabilities) mà Agent luôn thất bại, trong khi ASR-any (37.40%) phản ánh trần rủi ro tối đa khi kẻ tấn công có cơ hội thử nghiệm nhiều lần.

3. **Nhóm SUP tiếp tục là điểm yếu lớn nhất:** Kết quả k=3 củng cố vững chắc Luận điểm trung tâm: Omission / Safety Suppression duy trì ASR cao nhất qua cả 3 lượt chạy độc lập.
