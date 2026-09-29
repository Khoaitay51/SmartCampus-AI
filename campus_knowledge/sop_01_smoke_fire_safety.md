# QUY TRÌNH TIÊU CHUẨN (SOP-01): XỬ LÝ PHÁT HIỆN KHÓI & CẢNH BÁO CHÁY

- **Mã quy trình:** SOP-CAMPUS-FIRE-01
- **Phạm vi áp dụng:** Toàn bộ giảng đường, phòng thí nghiệm, phòng máy chủ khuôn viên SmartCampus.
- **Sự kiện liên quan (EventType):** `smoke_detected`, `emergency`

---

## 1. Mục tiêu & Nguyên tắc
1. **Bảo toàn tính mạng:** Ưu tiên phát hiện sớm, thoát hiểm an toàn và hỗ trợ lực lượng cứu hỏa.
2. **Loại trừ báo động giả:** Không kích hoạt còi hú toàn trường khi chỉ là 1 điểm nhiễu cảm biến đơn lẻ.
3. **Phân cấp xử lý:** Đi từ Cảnh báo mềm (Suspected) ➔ Cảnh báo khẩn cấp (Emergency).

---

## 2. Quy trình tra cứu dữ liệu (RAG Requirements)
Khi nhận sự kiện `smoke_detected`, Agent bắt buộc phải tra cứu:
1. `get_telemetry(room_id, metric='smoke', window='15m')`:
   - Xác định chỉ số khói tăng liên tục hay chỉ là xung nhiễu tức thời (spike 1 lần rồi biến mất).
2. `get_room_history(room_id, hours=6)`:
   - Kiểm tra phòng có tiền sử báo khói giả gần đây không, hoặc đây là lần đầu tiên cảm biến kích hoạt.
3. `compare_rooms(room_ids, metric='smoke', window='15m')` *(Nếu có phòng liền kề)*:
   - Phân biệt khói lan từ phòng khác sang hay phát sinh nội bộ trong phòng.

---

## 3. Ma trận quyết định hành động (Action Policy)

| Tình huống / Ngữ cảnh | Mức độ nguy cơ | Hành động khuyến nghị (Recommendation) | Thiết bị điều khiển (Action Tool) |
| :--- | :--- | :--- | :--- |
| **Khói chớm tăng nhẹ (Suspected)**<br>Chưa xác định ngọn lửa thật | Thấp / Trung bình | • Bật đèn LED vàng/cam cảnh báo tại phòng.<br>• Gửi thông báo đến ban quản lý kiểm tra.<br>• Bật quạt thông gió nếu có hệ thống hút khói. | `set_led`, `send_alert`, `set_fan` |
| **Khói tăng liên tục nhiều điểm**<br>Telemetry khẳng định nguy cơ cao | Cao | • Kích hoạt còi hú tại chỗ cảnh báo mọi người di tản.<br>• Gửi cảnh báo khẩn cấp tới Đội PCCC & An ninh. | `trigger_buzzer`, `send_alert` |
| **Tình trạng Khẩn cấp (Emergency)**<br>Đã xác nhận cháy hoặc FSM chuyển EMERGENCY | Nguy cấp | • Hú còi báo động khẩn cấp.<br>• Mở chốt cửa thoát hiểm tự động (sau khi xác thực quyền an toàn).<br>• Cắt nguồn thiết bị không thiết yếu. | `trigger_buzzer`, `set_door: open/unlocked`, `send_alert` |

---

## 4. Điều cấm & Lưu ý an toàn
- **Tuyệt đối không tự ý khóa cửa:** Không bao giờ dùng lệnh khóa cửa (`set_door: lock`) khi có cảnh báo khói.
- **Không tự mở cửa khi chỉ mới nghi ngờ (Suspected):** Cửa thoát hiểm chỉ mở khi đã xác định rõ tình huống khẩn cấp cần di tản, tránh kẻ gian lợi dụng báo động giả đột nhập.
