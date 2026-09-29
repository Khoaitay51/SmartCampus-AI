# QUY ĐỊNH VẬN HÀNH (SOP-03): QUẢN LÝ SĨ SỐ, CHẾ ĐỘ PHÒNG HỌC & KỲ THI (EXAM MODE)

- **Mã quy trình:** SOP-CAMPUS-ROOM-POLICY-03
- **Phạm vi áp dụng:** Chế độ vận hành phòng học (`room_mode`: LECTURE, EXAM, SAVING, LOCK, SUSPECTED).
- **Sự kiện liên quan (EventType):** `occupancy_change`, `manual_trigger`

---

## 1. Nguyên tắc cốt lõi theo Chế độ phòng (Room Mode)

### A. Chế độ Phòng thi (`EXAM` Mode)
- **Ưu tiên cao nhất:** Đảm bảo tính nghiêm túc và yên tĩnh tuyệt đối cho thí sinh làm bài.
- **Quy tắc bất di bất dịch:**
  - ❌ **CẤM TUYỆT ĐỐI** phát lệnh đổi trạng thái khóa/mở cửa (`set_door`) hoặc còi hú âm thanh (`trigger_buzzer`) trong giờ thi.
  - ✔️ Nếu nồng độ CO2 hoặc nhiệt độ phòng thi tăng cao ➔ Được phép bật quạt thông gió làm mát êm dịu (`set_fan`).
  - ✔️ Nếu phát hiện dấu hiệu bất thường ➔ Gửi cảnh báo im lặng (`send_alert`) tới giám thị phòng thi.

### B. Chế độ Giảng dạy (`LECTURE` Mode)
- Hệ thống hỗ trợ tối đa việc thông thoáng và điểm danh.
- Khi sinh viên vào lớp đông (sĩ số tăng), quạt và điều hòa được tự động điều phối theo ngưỡng vi khí hậu.

### C. Chế độ Tiết kiệm & Khóa (`SAVING` / `LOCK` Mode)
- Áp dụng ngoài giờ học (sau 17h30 hoặc ngày nghỉ).
- Mọi thiết bị không cần thiết phải được ngắt điện. Cửa phòng tự động khóa chốt an ninh.

---

## 2. Quy trình tra cứu dữ liệu (RAG Requirements)
Khi nhận sự kiện `occupancy_change`:
1. `get_schedule(room_id)`:
   - Tra cứu phòng hiện tại có lịch học, lịch thi, hay hội thảo nào được phê duyệt không.
2. `get_attendance(room_id)`:
   - Đối chiếu số người đếm được từ camera/cảm biến với danh sách điểm danh thực tế của lớp.
3. `get_room_history(room_id, hours=2)`:
   - Kiểm tra xem sĩ số tăng đột ngột hay tăng dần dần trong khoảng chuyển giao tiết học.

---

## 3. Ma trận quyết định hành động (Action Policy)

| Kịch bản sĩ số | Phân tích ngữ cảnh | Hành động khuyến nghị | Tool sử dụng |
| :--- | :--- | :--- | :--- |
| **Sĩ số tăng trong giờ thi (`EXAM`)** | Thí sinh vào phòng thi đầy đủ | Giữ nguyên trạng thái yên tĩnh, theo dõi nhiệt độ | `skip: true` (hoặc `set_fan` nếu nóng) |
| **Sĩ số tăng ngoài giờ học (`SAVING`/`LOCK`)** | Không có lịch học nhưng phát hiện có người trong phòng | Nghi ngờ tụ tập trái phép hoặc xâm nhập sau giờ học ➔ Báo bảo vệ | `send_alert` |
| **Sĩ số tăng gấp đôi vượt quá sức chứa phòng** | Nguy cơ quá tải hoặc lớp học ghép chưa thông báo | Bật quạt thông gió tối đa + gửi thông báo điều tiết phòng | `set_fan: on`, `send_alert` |
| **Sĩ số giảm về 0 sau giờ học** | Lớp học đã tan | Chuyển phòng sang chế độ tiết kiệm điện năng | `set_mode: SAVING` |

---

## 4. Điều kiện an toàn
- AI Agent **không được tự tiện ra quyết định khóa nhốt người** trong phòng (`set_door: lock`) khi cảm biến còn ghi nhận người bên trong (`occupancy > 0`).
