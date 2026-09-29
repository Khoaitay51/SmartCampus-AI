# QUY TRÌNH TIÊU CHUẨN (SOP-02): ĐIỀU TIẾT NHIỆT ĐỘ, THÔNG GIÓ & TIẾT KIỆM NĂNG LƯỢNG

- **Mã quy trình:** SOP-CAMPUS-HVAC-02
- **Phạm vi áp dụng:** Các phòng học, phòng thi, giảng đường lớn và phòng thực hành máy tính.
- **Sự kiện liên quan (EventType):** `temperature_anomaly`

---

## 1. Tiêu chuẩn môi trường vi khí hậu
- **Nhiệt độ phòng học tiêu chuẩn:** 22.0°C – 26.0°C.
- **Ngưỡng kích hoạt làm mát:** Khi nhiệt độ vượt quá 28.0°C trong giờ học.
- **Ngưỡng quá nhiệt nghiêm trọng:** Khi nhiệt độ phòng vượt 35.0°C – 40.0°C (nguy cơ sốc nhiệt hoặc hỏng hóc thiết bị điện tử).

---

## 2. Quy trình tra cứu dữ liệu (RAG Requirements)
Khi nhận sự kiện `temperature_anomaly`:
1. `get_telemetry(room_id, metric='temperature', window='1h')`:
   - Phân tích xu hướng 1 giờ qua: Nhiệt độ đang tăng nhanh, tăng chậm hay đang có dấu hiệu đi xuống.
2. `get_predictions(room_id, metric='temperature', horizon='15m')`:
   - Dùng mô hình dự báo EWMA xem trong 15 - 30 phút tới nhiệt độ có tiếp tục vượt ngưỡng 32°C - 34°C hay không để tránh hành động bật quạt thừa nếu nhiệt độ sắp tự giảm.
3. `compare_rooms(room_ids, metric='temperature', window='1h')`:
   - So sánh với các phòng lân cận cùng tầng: Nếu chỉ 1 phòng bị nóng ➔ Bất thường cục bộ. Nếu cả dãy phòng cùng tăng nhiệt độ ➔ Nghi ngờ hỏng cụm máy lạnh/chiller trung tâm toàn tòa nhà.
4. `get_schedule(room_id)` & `get_room_history(room_id)`:
   - Xác nhận lớp có đang học đông người không, và agent đã đề xuất bật quạt/điều hòa trong 60 giây qua chưa (cooldown).

---

## 3. Ma trận quyết định hành động (Action Policy)

| Kịch bản phân tích | Đánh giá nguyên nhân | Hành động khuyến nghị | Tool sử dụng |
| :--- | :--- | :--- | :--- |
| **Nhiệt độ đang tăng và dự báo EWMA tiếp tục tăng** (> 30°C) | Phòng bí khí, đông sinh viên hoặc điều hòa yếu | Bật quạt thông gió để lưu thông không khí và hạ nhiệt | `set_fan: on` |
| **Nhiệt độ nhiều phòng cùng tăng vọt đồng thời** | Sự cố hệ thống làm mát trung tâm (HVAC/Chiller hỏng) | Gửi cảnh báo kỹ thuật để đội bảo trì can thiệp tòa nhà | `send_alert` (thay vì chỉ bật quạt 1 phòng) |
| **Nhiệt độ vượt ngưỡng nguy hiểm** (> 40°C) | Nguy cơ chập cháy thiết bị hoặc phòng máy chủ quá nhiệt | Kích hoạt còi hú cảnh báo người ra ngoài + gửi cảnh báo | `trigger_buzzer`, `send_alert` |
| **Nhiệt độ tăng nhưng dự báo giảm** hoặc phòng không có người | Nhiễu tạm thời hoặc phòng trống | Bỏ qua không can thiệp để tiết kiệm điện năng | `skip: true` |

---

## 4. Quy định an toàn
- **Chế độ cooldown:** Tuyệt đối không gửi liên tiếp lệnh bật quạt cho cùng 1 phòng trong vòng 60 giây.
- **Tiết kiệm điện:** Khi phòng chuyển sang chế độ `SAVING` (sau giờ học), toàn bộ quạt và thiết bị làm mát phải được tắt.
