# QUY TRÌNH TIÊU CHUẨN (SOP-04): KIỂM SOÁT THẺ RFID LẠ & AN NINH RA VÀO

- **Mã quy trình:** SOP-CAMPUS-SECURITY-04
- **Phạm vi áp dụng:** Hệ thống đầu đọc thẻ RFID gắn tại cửa các phòng học, phòng thí nghiệm chuyên đề, phòng ban bộ môn.
- **Sự kiện liên quan (EventType):** `rfid_unknown`

---

## 1. Mục tiêu kiểm soát
1. **Phân biệt quẹt thẻ nhầm vs Hành vi xâm nhập:** Tránh báo động sai làm ảnh hưởng sinh viên quẹt nhầm phòng.
2. **Ngăn chặn dò thẻ / tấn công Brute-force:** Phát hiện và ngăn chặn người cố tình quẹt liên tục nhiều thẻ lạ ngoài giờ học.
3. **Bảo vệ tài sản trường học:** Giữ an toàn cho phòng máy tính, phòng thiết bị giá trị cao sau giờ làm việc.

---

## 2. Quy trình tra cứu dữ liệu (RAG Requirements)
Khi nhận sự kiện `rfid_unknown`:
1. `get_schedule(room_id)`:
   - Kiểm tra thời điểm quẹt thẻ phòng có đang trong khung giờ học/dạy hợp lệ hay không.
2. `get_room_history(room_id, hours=24)`:
   - Kiểm tra lịch sử 24h qua: Thẻ lạ này đã từng quẹt chưa? Có bao nhiêu lượt quẹt không hợp lệ liên tiếp trong thời gian ngắn?
3. `get_attendance(room_id)` *(Nếu đang trong giờ học)*:
   - Kiểm tra xem có sinh viên nào đi học bù hoặc giáo viên trợ giảng mới chưa cập nhật danh sách thẻ hay không.
4. `search_history(query='rfid_unknown quẹt thẻ lạ')`:
   - Tìm kiếm các sự vụ vi phạm an ninh tương tự trong quá khứ tại phòng hoặc tầng này.

---

## 3. Ma trận quyết định hành động (Action Policy)

| Tình huống thực tế | Phân tích rủi ro | Hành động khuyến nghị | Tool sử dụng |
| :--- | :--- | :--- | :--- |
| **Quẹt thẻ lạ trong giờ có lớp học** | Sinh viên học bù, sinh viên vào nhầm lớp hoặc thẻ mới cấp chưa đồng bộ | Bỏ qua, để giảng viên/lớp trưởng kiểm tra điểm danh thủ công | `skip: true` |
| **Quẹt thẻ lạ ngoài giờ học** (Sau 17h30, phòng đang `SAVING`/`LOCK`) | Nghi vấn người lạ tiếp cận phòng học đóng cửa sau giờ hành chính | Gửi cảnh báo an ninh cho bảo vệ ca trực tới kiểm tra | `send_alert` |
| **Quẹt thẻ lạ lặp lại nhiều lần liên tiếp** | Nghi ngờ hành vi dò thẻ (brute-force) hoặc cố tình phá hoại khóa cửa | Kích hoạt còi hú tại chỗ cảnh cáo kẻ xâm nhập + báo động đỏ | `trigger_buzzer`, `send_alert` |
| **Thẻ hợp lệ nhưng phòng đang khóa đặc biệt** (`SUSPECTED`) | Phòng đang niêm phong hoặc cách ly kỹ thuật | Từ chối mở cửa, gửi thông báo lý do phòng đang khóa | `send_alert` |

---

## 4. Điều cấm an ninh
- **Không bao giờ tự ý mở khóa cửa (`set_door: unlock/open`):** Khi có sự kiện `rfid_unknown`, AI Agent tuyệt đối không được tự động mở cửa cho người quét thẻ lạ nếu chưa có sự phê duyệt từ hệ thống phân quyền Backend hoặc bảo vệ.
