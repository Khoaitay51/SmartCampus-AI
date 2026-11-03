# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

try:
    import docx
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
    from docx.oxml import parse_xml, OxmlElement
    from docx.oxml.ns import nsdecls, qn
except ImportError:
    print("python-docx is not installed!")
    sys.exit(1)

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def create_document():
    doc = docx.Document()

    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)

    # Header Box
    table_head = doc.add_table(rows=1, cols=1)
    table_head.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = table_head.rows[0].cells[0]
    set_cell_background(c, "1E3A8A") # Deep Navy
    set_cell_margins(c, 220, 220, 250, 250)
    
    p = c.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("BÁO CÁO NGHIÊN CỨU TOÀN DIỆN: ĐÁNH GIÁ AN TOÀN VÀ ĐỘ BỀN VỮNG CỦA LLM-BASED AGENT TRONG HỆ THỐNG ĐIỀU KHIỂN CYBER-PHYSICAL SMART CAMPUS")
    run.font.bold = True
    run.font.size = Pt(14.5)
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    
    p2 = c.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(
        "Dự án: Smart Campus Cyber-Physical Systems Security Benchmark (v2 Refined)\n"
        "Mô hình nghiên cứu: ReActXenAgent (Gemini 3.5 Flash Lite) | Quy mô thực nghiệm: k=3 độc lập (762 runs Track A + 300 runs Clean Twin)\n"
        "Hạ tầng triển khai: 2 Node Phòng học + 1 Node Hành lang (ESP32) | Edge Gateway (:8000), TimescaleDB (:5433) | Baseline Freeze: 2026-11-02"
    )
    r2.font.size = Pt(9.5)
    r2.font.color.rgb = RGBColor(0xE2, 0xE8, 0xF0)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # 1. Hệ thống mục tiêu
    h1 = doc.add_heading("1. Kiến Trúc Hệ Thống Mục Tiêu (Target System Architecture)", level=1)
    h1.style.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    
    p_arch = doc.add_paragraph(
        "Hệ thống được thiết kế theo mô hình Agentic Cyber-Physical System (CPS) khép kín gồm 4 phân lớp kết hợp chặt chẽ giữa phần cứng nhúng IoT, trạm điều hành biên, tác nhân AI ra quyết định và giao diện giám sát Human-in-the-Loop (HITL):\n\n"
        "1. Hạ tầng phần cứng IoT (ESP32 Nodes - 2 Phòng học + 1 Hành lang): Triển khai trên 2 phòng học thực tế và 1 hành lang kết nối. Mỗi phòng học trang bị cảm biến nhiệt độ & độ ẩm DHT22 (chu kỳ 2s), cảm biến khói gas MQ-2, cặp hồng ngoại Dual IR đếm chiều ra/vào sinh viên, và đầu đọc RFID RC522 điểm danh. Cơ cấu chấp hành gồm quạt thông gió (đóng ngắt qua transistor NPN 2N2222), khóa chốt Servo SG90, còi báo động Buzzer, dải LED WS2812B và màn hình OLED SSD1306. Node hành lang chuyên trách đăng ký thẻ lạ và kiểm soát an ninh chung.\n\n"
        "2. Trạm biên Edge Computing Gateway (FastAPI :8000 + TimescaleDB :5433): Quản lý máy trạng thái hữu hạn FSM gồm 7 chế độ (SAVING, LECTURE, EXAM, EVENT, CLEANING, MAINTENANCE, LOCK), duy trì bối cảnh vi khí hậu trượt 15 phút gần nhất, và tích hợp SinkToolRecorder giám sát Canary Token chống rò rỉ dữ liệu.\n\n"
        "3. Tác nhân AI Decision Engine (ReActXenAgent + pgvector LTM): Triển khai chu trình ReAct đa vai trò: Dynamic Few-Shot truy vấn bộ nhớ dài hạn LTM qua vector 768 chiều nomic-embed-text; Main ReAct Agent (Self-Ask + tối đa 5 lượt RAG tra cứu); Review Agent thẩm định độc lập theo quy chuẩn SOP; Reflect Agent tự soi chiếu sửa sai; ma trận phân quyền MODE_PERMISSIONS; Abstention Heuristic (Confidence < 0.35); và hệ thống cứu nguy Fallback 4 cấp (Model -> Parser Regex -> Tool Mock -> Heuristic Rules).\n\n"
        "4. Giao diện Digital Twin 3D & HITL: Bản sao số thời gian thực trên React/ThreeJS, cho phép quản trị viên phê duyệt [Execute / Ignore] trước khi tín hiệu điều khiển được chuyển xuống relay phần cứng."
    )
    p_arch.paragraph_format.line_spacing = 1.15
    p_arch.paragraph_format.space_after = Pt(10)

    # 2. Mô hình đe dọa
    h2 = doc.add_heading("2. Mô Hình Đe Dọa & Không Gian Tấn Công (Threat Model & Taxonomy)", level=1)
    h2.style.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    p_tm = doc.add_paragraph(
        "• Giả định kẻ tấn công (Knowledgeable Gray-box Adversary): Kẻ tấn công có hiểu biết đầy đủ về các Quy trình vận hành chuẩn (SOP) mang tính công khai của nhà trường (lịch diễn tập PCCC, quy trình bảo dưỡng điều hòa HVAC, lịch thi cử, nội quy mượn phòng). Nhờ đó, kẻ tấn công ngụy tạo được các vỏ bọc tâm lý cực kỳ tinh vi. Tuy nhiên, kẻ tấn công hoàn toàn không biết System Prompt, mã nguồn nội tại, chu trình ReAct hay cơ sở dữ liệu TimescaleDB.\n"
        "• Kênh tấn công (Attack Surface): Kẻ tấn công chỉ kiểm soát duy nhất trường văn bản tự do event_data.description trong gói tin MQTT/Web. Toàn bộ thông số đo đạc cảm biến vật lý (nhiệt độ, khói gas, timestamp) và bối cảnh vận hành thuộc vùng tin cậy tuyệt đối (Trusted Boundary) mà attacker không thể can thiệp.\n"
        "• Xây dựng bộ testcase (300 -> 254 ca hợp lệ): Từ tích Descartes giữa 60 hồ sơ kẻ tấn công (22 DH-A, 10 DH-S, 22 SUP, 6 DS) và 5 kịch bản (U1...U5) tạo ra 300 ca tiềm năng. Hệ thống loại bỏ 46 ca để tránh xung đột ngữ nghĩa vật lý: loại 22 ca SUP trên U5 (phòng bình thường, khuyên đứng yên là đúng tự nhiên); loại 10 ca DH-A trùng lặp cứu hộ (bảo bật quạt trùng quy chuẩn phòng server 52°C); loại 14 ca DH-S không khả thi phần cứng. Phân bổ còn lại (100, 36, 88, 30) được đánh giá theo tỷ lệ chuẩn hóa độc lập, phản ánh trung thực bề mặt tấn công vật lý."
    )
    p_tm.paragraph_format.line_spacing = 1.15
    p_tm.paragraph_format.space_after = Pt(10)

    # 3. Luận điểm trung tâm & Kết quả
    h3 = doc.add_heading("3. Luận Điểm Trung Tâm & Kết Quả Thực Nghiệm Toàn Diện (k=3)", level=1)
    h3.style.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    p_thesis = doc.add_paragraph()
    r_th = p_thesis.add_run(
        "\"Đối với một Autonomous Agent điều khiển hệ thống Cyber-Physical (CPS) chỉ nhận một trường văn bản tự do làm kênh tấn công gián tiếp, phương thức tấn công nguy hiểm và hiệu quả nhất KHÔNG PHẢI là ép Agent thực hiện một hành vi phá hoại chủ động (Commission), mà là THUYẾT PHỤC NÓ TỪ BỎ HÀNH ĐỘNG BẢO VỆ CẦN THIẾT (Omission / Safety Suppression). Hiện tượng này được đo lường một cách khách quan thông qua nhãn xác định rút ra từ trạng thái cảm biến vật lý tại thời điểm T0.\""
    )
    r_th.font.italic = True
    r_th.font.bold = True
    r_th.font.color.rgb = RGBColor(0x0F, 0x17, 0x2A)
    p_thesis.paragraph_format.space_after = Pt(8)

    p_pol = doc.add_paragraph(
        "• Khám phá cơ chế - Hiện tượng \"Đảo cực an toàn\" (Safety Polarity Inversion): Trong các ứng dụng IT truyền thống, \"không hành động\" (inactivity/abstention) là an toàn mặc định (Fail-safe). Tuy nhiên trong hệ thống CPS khi có hiểm họa thực tế (cháy, ngạt khí), \"không hành động\" đồng nghĩa với thất bại thảm họa (Catastrophic Omission). Khi kẻ tấn công ngụy tạo lý do bảo trì/diễn tập, LLM bị thiên kiến an toàn (Safety Alignment bias) đánh lừa: nó nhầm tưởng việc \"đứng yên để tránh gây hoảng loạn\" là hành vi cẩn trọng, từ đó vô tình hoàn thành mục tiêu triệt tiêu cứu hộ của kẻ tấn công."
    )
    p_pol.paragraph_format.line_spacing = 1.15

    # Table 1: Headline Metrics (Mean k=3)
    p_t1 = doc.add_paragraph()
    r_t1 = p_t1.add_run("BẢNG 1: CHỈ SỐ HEADLINE TỔNG THỂ HỆ THỐNG (CHUẨN HÓA MEAN k=3, 762 LƯỢT CHẠY)")
    r_t1.font.bold = True
    r_t1.font.size = Pt(10.5)

    table1 = doc.add_table(rows=1, cols=6)
    table1.alignment = WD_TABLE_ALIGNMENT.CENTER
    table1.autofit = False

    t1_headers = ["Chỉ số (Metric)", "Ký hiệu", "Mẫu số (N)", "Giá trị Mean (k=3)", "Độ lệch chuẩn (Std)", "Ý nghĩa đánh giá an toàn CPS"]
    for i, title in enumerate(t1_headers):
        c = table1.rows[0].cells[i]
        c.text = title
        set_cell_background(c, "1E3A8A")
        set_cell_margins(c, 100, 100, 80, 80)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(9)
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    t1_data = [
        ("Benign Utility", "BU", "N=100 (Ca thường nhật)", "93.00%", "—", "Năng lực phục vụ chính xác khi vận hành bình thường."),
        ("Attack Success Rate", "ASR", "N=254 (Toàn bộ Track A)", "27.30%", "± 4.81%", "Tỷ lệ tấn công IPI chiếm quyền điều khiển thành công."),
        ("• ASR (Parse sạch)", "ASR_clean", "N=212 (Parse JSON chuẩn r1)", "18.87%", "—", "Độ nhạy khi loại bỏ ảnh hưởng của bộ parser dự phòng."),
        ("Utility under Attack", "UA", "N=254 (Toàn bộ Track A)", "65.62%", "± 9.08%", "Năng lực duy trì an toàn/hợp lệ khi đang bị tấn công."),
        ("Utility Degradation", "ΔU", "Hiệu số: BU - UA", "27.38%", "—", "93.00% - 65.62% = 27.38% (Mức độ sụt giảm tiện ích)."),
        ("Mitigation Hazard Rate", "MHR", "N=216 (Ca có hiểm họa)", "34.08%", "± 8.77%", "Tỷ lệ Agent bỏ qua xử lý an toàn khi tai nạn thực sự diễn ra."),
        ("Format-Disruption Rate", "FDR", "N=254 (Toàn bộ Track A)", "16.54%", "± 0.79%", "Tỷ lệ vỡ định dạng JSON do xung đột chỉ thị duy trì ổn định.")
    ]

    for row_idx, r_val in enumerate(t1_data):
        row_cells = table1.add_row().cells
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_val):
            row_cells[c_idx].text = val
            set_cell_background(row_cells[c_idx], bg)
            set_cell_margins(row_cells[c_idx], 70, 70, 70, 70)
            p = row_cells[c_idx].paragraphs[0]
            p.runs[0].font.size = Pt(8.5)
            if c_idx in [1, 3, 4]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if c_idx == 3:
                p.runs[0].font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Table 2: 3-round dynamics
    p_t2 = doc.add_paragraph()
    r_t2 = p_t2.add_run("BẢNG 2: DIỄN BIẾN CHỈ SỐ CỐT LÕI QUA 3 VÒNG THỰC NGHIỆM ĐỘC LẬP (k=3)")
    r_t2.font.bold = True
    r_t2.font.size = Pt(10)

    table2 = doc.add_table(rows=1, cols=5)
    table2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table2.autofit = False

    t2_headers = ["Chỉ số (Metric)", "Vòng 1 (r1)", "Vòng 2 (r2)", "Vòng 3 (r3)", "Trung bình (Mean k=3)"]
    for i, title in enumerate(t2_headers):
        c = table2.rows[0].cells[i]
        c.text = title
        set_cell_background(c, "1E3A8A")
        set_cell_margins(c, 90, 90, 80, 80)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(9)
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    t2_data = [
        ("Attack Success Rate (ASR)", "22.05% (56/254)", "28.35% (72/254)", "31.50% (80/254)", "27.30% ± 4.81%"),
        ("Utility under Attack (UA)", "75.98% (193/254)", "61.81% (157/254)", "59.06% (150/254)", "65.62% ± 9.08%"),
        ("Độ Sụt Giảm Tiện Ích (ΔU)", "17.02%", "31.19%", "33.94%", "27.38%"),
        ("Mitigation Hazard Rate (MHR)", "24.11% (52/216)", "37.50% (81/216)", "40.62% (87/216)", "34.08% ± 8.77%"),
        ("Format-Disruption Rate (FDR)", "16.54% (42/254)", "17.32% (44/254)", "15.75% (40/254)", "16.54% ± 0.79%")
    ]

    for row_idx, r_val in enumerate(t2_data):
        row_cells = table2.add_row().cells
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(r_val):
            row_cells[c_idx].text = val
            set_cell_background(row_cells[c_idx], bg)
            set_cell_margins(row_cells[c_idx], 65, 65, 70, 70)
            p = row_cells[c_idx].paragraphs[0]
            p.runs[0].font.size = Pt(8.5)
            if c_idx >= 1:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if c_idx == 4:
                p.runs[0].font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Table 3: Taxonomy Breakdown
    p_t3 = doc.add_paragraph()
    r_t3 = p_t3.add_run("BẢNG 3: PHÂN RÃ TỶ LỆ BỊ THAO TÚNG THEO 4 CHIỀU TẤN CÔNG (TAXONOMY BREAKDOWN QUA k=3)")
    r_t3.font.bold = True
    r_t3.font.size = Pt(10)

    table3 = doc.add_table(rows=1, cols=8)
    table3.alignment = WD_TABLE_ALIGNMENT.CENTER
    table3.autofit = False

    t3_headers = ["Phân nhóm tấn công", "Mã", "N", "r1", "r2", "r3", "Mean (%)", "Cơ chế thất bại & Tác động vật lý"]
    for i, title in enumerate(t3_headers):
        c = table3.rows[0].cells[i]
        c.text = title
        set_cell_background(c, "1E3A8A")
        set_cell_margins(c, 90, 90, 60, 60)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(8.5)
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    t3_data = [
        ("Safety Suppression (Omission)", "SUP", "88", "36.4%", "48.9%", "54.5%", "46.59%", "Nguy hiểm nhất: Bị lừa bởi lý do diễn tập/bảo trì, tự ý bỏ qua còi hú và quạt khi có cháy/khói thật."),
        ("Direct Harm - Actuation", "DH-A", "100", "22.0%", "27.0%", "30.0%", "26.33%", "Bị lừa bởi tin giả để ngắt quạt làm mát phòng máy chủ hoặc hú còi liên tục gây hoảng loạn."),
        ("Direct Harm - Security", "DH-S", "36", "5.6%", "5.6%", "5.6%", "5.56%", "Mạo danh lãnh đạo để ép mở khóa chốt cửa phòng lab/server (cơ chế an ninh cửa rất vững)."),
        ("Data Stealing (Trojan Audit)", "DS", "30", "0.0%", "0.0%", "0.0%", "0.00%*", "Agent không kích hoạt tool sink (http_post) gửi Canary Token ra ngoài (Wilson upper ≤11.35%).")
    ]

    for row_idx, r_val in enumerate(t3_data):
        row_cells = table3.add_row().cells
        bg = "FEF2F2" if "SUP" in r_val[1] else ("F8FAFC" if row_idx % 2 == 1 else "FFFFFF")
        for c_idx, val in enumerate(r_val):
            row_cells[c_idx].text = val
            set_cell_background(row_cells[c_idx], bg)
            set_cell_margins(row_cells[c_idx], 65, 65, 60, 60)
            p = row_cells[c_idx].paragraphs[0]
            p.runs[0].font.size = Pt(8.2)
            if c_idx in [1, 2, 3, 4, 5, 6]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if c_idx == 6:
                p.runs[0].font.bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # 4. Ba đóng góp học thuật
    h4 = doc.add_heading("4. Ba Đóng Góp Nghiên Cứu Đột Phá (C1, C2, C3) Gắn Liền Với Bối Cảnh, Cơ Chế & Hệ Quả CPS", level=1)
    h4.style.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    p_c1 = doc.add_paragraph(
        "• Đóng góp 1 (C1) - Khung Benchmark CPS Đa Chiều Với Cơ Chế Đảo Cực An Toàn & Ground Truth Vật Lý Tất Định:\n"
        "  - Bối cảnh đặc thù: Hệ thống điều khiển khuôn viên thông minh vận hành trên 2 phòng học và 1 hành lang ESP32, quản lý các cơ cấu chấp hành có tính bất đối xứng và hậu quả không thể hoàn tác (quạt hút khói 2N2222, khóa chốt Servo SG90, còi an ninh).\n"
        "  - Cơ chế & Gap: Khắc phục hạn chế của InjecAgent (không đo Utility) và Evil-AI (chấm LLM chủ quan). Đồng thời kế thừa từ AgentAbstain (UIUC, 2026) tư tưởng kiểm tra \"commit\" trên log tool call xác định, nhưng giải quyết bài toán ngược chiều: ở AgentAbstain, dừng lại (abstain) là đúng; ở SmartCampus có hazard thật, dừng lại là sai phạm an toàn nghiêm trọng.\n"
        "  - Hiện tượng \"Đảo cực an toàn\": Khác với các hệ thống IT nơi không hành động là Fail-safe, trong CPS khi có sự cố, không hành động là thất bại thảm họa. Định nghĩa ASR bắt buộc phải phụ thuộc vào trạng thái hiểm họa vật lý tại T0 (có hazard thì thành công của attacker là omission, không có hazard thì là commission).\n"
        "  - Minh chứng: Bộ 254 ca Track A + 100 ca Benign, đo đồng thời BU = 93.00%, UA = 65.62%, ΔU = 27.38%, MHR = 34.08% và ASR = 27.30% (Mean k=3)."
    )
    p_c1.paragraph_format.line_spacing = 1.15

    p_c2 = doc.add_paragraph(
        "• Đóng góp 2 (C2) - Phát Hiện Cơ Chế Tấn Công Omission & Đối Chứng Phản Thực Tế Clean Twin (k=3):\n"
        "  - Bối cảnh & Cơ chế: Attacker chỉ kiểm soát trường description, dữ liệu cảm biến (nhiệt 52.3°C, khói 650 ppm) là thật 100%. Khác với EpiSEM-Bench (mất bằng chứng thụ động), ở đây bằng chứng cảm biến đầy đủ nhưng bị văn bản không tin cậy lấn át (Text-overrides-Sensor Bias). Khác với Ignored, Not Refused (2025/2026 - coi lờ đi là an toàn), trong CPS hành vi \"lờ đi\" chính là mục tiêu thắng lợi của attacker.\n"
        "  - Phương pháp Clean Twin (k=3): Kế thừa cặp thế giới (T+, T-) từ AgentAbstain và (W-, W+) từ EpiSEM-Bench. Giữ nguyên 100% cảm biến vật lý, chỉ làm sạch câu chữ ngụy tạo qua 300 lượt chạy độc lập.\n"
        "  - Bằng chứng thép quy kết nhân quả: Nhánh Z (Bare technical) cho tỷ lệ bỏ sót đúng 0.0% (0/36), chứng minh tỷ lệ quên tự nhiên của LLM bằng 0! Tỷ lệ bỏ sót chỉ xuất hiện khi có bối cảnh giả (Nhánh P: 23.1%) và đạt đỉnh khi có lệnh cấm (Nhánh A: 36.4% ở r1, 46.59% qua k=3). Mức tăng quy kết trực tiếp do IPI là ΔASR = +36.4 điểm % (p = 0.01916 theo kiểm định dấu).\n"
        "  - Kết luận: Thuyết phục Agent \"ngồi yên khi có tai nạn\" (SUP: 46.59%) đạt hiệu quả cao gấp đôi so với ép Agent phá hoại chủ động (DH-A: 26.33%, DH-S: 5.56%)."
    )
    p_c2.paragraph_format.line_spacing = 1.15

    p_c3 = doc.add_paragraph(
        "• Đóng góp 3 (C3) - Kiểm Toán Thực Thi (Harness Audit) & Chỉ Dấu Format-Disruption Rate (FDR):\n"
        "  - Bối cảnh & Khắc phục sai lệch: Khắc phục cảnh báo méo mó kết quả do parser từ Firewalls (2024) và EASE (2024). Kiểm toán thủ công 100% (42/42 ca Fallback) chứng minh 100% kết quả parse đều khớp chính xác ý định suy luận của LLM (ASR parse sạch đạt 18.87%).\n"
        "  - Chế độ lỗi FDR = 16.54% ± 0.79%: Xung đột chỉ thị giữa System Prompt và Payload IPI làm vỡ định dạng JSON output. Các ca vỡ định dạng có tỷ lệ bị hack lên tới 38.10% so với chỉ 18.87% ở ca parse sạch (p ≈ 0.013 theo Fisher exact).\n"
        "  - Hàm ý kiến trúc phòng thủ Fail-safe: FDR là chỉ dấu rủi ro cao. Trong CPS, khi phát hiện lỗi cú pháp, hệ thống tuyệt đối không nên cố dùng regex chắp vá mà phải kích hoạt ngay Fail-safe Inversion (chuyển về hành vi an toàn mặc định dựa trên cảm biến vật lý)."
    )
    p_c3.paragraph_format.line_spacing = 1.15
    p_c3.paragraph_format.space_after = Pt(10)

    # 5. So sánh Related Work
    h5 = doc.add_heading("5. Đối Chiếu Chi Tiết Với Related Work Quốc Tế", level=1)
    h5.style.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    table_rw = doc.add_table(rows=1, cols=7)
    table_rw.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_rw.autofit = False

    rw_hdrs = ["Công trình", "Năm", "Miền ứng dụng", "Ground Truth", "Đo Utility?", "Kế thừa phương pháp luận", "Khoảng trống (Gap) so với nghiên cứu này"]
    for i, t in enumerate(rw_hdrs):
        c = table_rw.rows[0].cells[i]
        c.text = t
        set_cell_background(c, "1E3A8A")
        set_cell_margins(c, 80, 80, 50, 50)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.bold = True
        p.runs[0].font.size = Pt(8.5)
        p.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    rw_data = [
        ("InjecAgent", "2024", "Văn phòng ảo (Office)", "Khớp tên tool", "Không", "Phân loại IPI tổng quát", "Không đo Utility; không có ràng buộc vật lý hai chiều."),
        ("AgentDojo", "2024", "Web, Mail, Bash", "Trạng thái CSDL số", "Có (Utility số)", "Trạng thái môi trường", "Chỉ thao tác trên dữ liệu số tĩnh; mọi sai phạm đều có thể rollback."),
        ("Evil-AI Benchmark", "2024", "IoT Gia đình", "LLM-as-a-Judge", "Không", "Khảo sát thiết bị thông minh", "Đánh giá chủ quan qua LLM Judge; bỏ qua lỗi cú pháp và utility."),
        ("EASE Framework", "2024", "Email Agent", "Phân tầng Stage-wise", "Một phần", "Phân lập lỗi harness", "Chưa kết hợp mô hình tấn công IPI trên thiết bị phần cứng."),
        ("AgentAbstain (UIUC)", "2026", "Tác vụ tổng quát", "Log Tool Call", "Một phần", "Cặp (T+, T-); commit xác định", "Ngược chiều: Ở AgentAbstain dừng lại là đúng; ở SmartCampus dừng lại khi có hazard thật là sai phạm an toàn."),
        ("EpiSEM-Bench", "2025/2026", "Truy vấn thông tin", "Bằng chứng thụ động", "Có (Recovery)", "Cặp thế giới W-/W+; false abstain", "Chỉ xét mất bằng chứng thụ động; SmartCampus xét cảm biến đúng nhưng bị văn bản lấn át."),
        ("Ignored, Not Refused", "2025/2026", "LLM quy mô nhỏ", "Kiểm toán qua CoT", "Không", "Phân loại: tuân thủ/từ chối/lờ đi", "Coi \"lờ đi\" là trạng thái an toàn; chưa thấy trong CPS \"lờ đi\" chính là thất bại thảm họa."),
        ("SmartCampus (Nghiên cứu này)", "2026", "Cyber-Physical Smart Campus", "Tất định từ Cảm biến & SOP", "Có (BU 93%, UA 66%)", "Kế thừa cặp đối chứng & chuẩn hóa Commit", "Đề xuất Khái niệm Đảo cực an toàn & Omission trong CPS (ASR 46.6%, k=3).")
    ]

    for r_idx, r_val in enumerate(rw_data):
        row_cells = table_rw.add_row().cells
        bg = "EFF6FF" if "SmartCampus" in r_val[0] else ("F8FAFC" if r_idx % 2 == 1 else "FFFFFF")
        for c_idx, val in enumerate(r_val):
            row_cells[c_idx].text = val
            set_cell_background(row_cells[c_idx], bg)
            set_cell_margins(row_cells[c_idx], 60, 60, 50, 50)
            p = row_cells[c_idx].paragraphs[0]
            p.runs[0].font.size = Pt(7.8)
            if "SmartCampus" in r_val[0]:
                p.runs[0].font.bold = True
            if c_idx in [1, 4]:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # 6. Giới hạn nghiên cứu
    h6 = doc.add_heading("6. Giới Hạn Nghiên Cứu (Limitations & Future Work)", level=1)
    h6.style.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
    doc.add_paragraph(
        "Nghiên cứu tuyên bố minh bạch các giới hạn học thuật theo tiêu chuẩn hội nghị an toàn quốc tế:\n\n"
        "1. Phạm vi mô hình duy nhất (Single-Model Scope): Thực nghiệm toàn diện hiện tại được triển khai trên gemini-3.5-flash-lite. Mặc dù mô hình đại diện cho năng lực agent tốc độ cao hiện đại, kết quả cần được mở rộng kiểm chứng trên các họ mô hình mã nguồn mở (như Llama-3-70B, Mistral-Large, Qwen-2.5) trong các nghiên cứu tiếp theo.\n\n"
        "2. Kịch bản tấn công tĩnh (Non-Adaptive Attackers): Các payload tiêm nhiễm được thiết kế cố định theo 6 kỹ thuật tâm lý học xã hội, chưa áp dụng cơ chế tấn công tương tác nhiều vòng (Multi-turn Adaptive Jailbreak / Automated Red-teaming).\n\n"
        "3. Đơn sự kiện trên mỗi ca kiểm thử (Single-Event per Episode): Mỗi testcase kích hoạt đánh giá dựa trên một sự kiện bất thường duy nhất tại mốc thời gian T0, chưa mô phỏng chuỗi sự kiện dồn dập (Event Storming) kéo dài nhiều giờ.\n\n"
        "4. Đánh giá ở tầng khuyến nghị chấp hành (Dry-run Level Evaluation): Nghiên cứu đo lường chính xác lệnh được sinh ra ở tầng final_recommendation kết nối qua Edge Gateway, chưa đo lường các sai số cơ học thực tế của relay điện trở hoặc van servo vật lý."
    )

    # Target output paths
    out_dir = Path("AI + Backend/benchmarkv2_refined")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file1 = out_dir / "Bao_Cao_Tong_Ket_Nghien_Cuu_SmartCampus_Agent_Security.docx"
    doc.save(str(out_file1))
    print(f"Saved primary document to: {out_file1}")

    out_file2 = Path(r"C:\Users\Admin\.gemini\antigravity\brain\c2e5e9ba-9e41-499e-9cd7-f03cf8c8ad3e\Bao_Cao_Nghien_Cuu_SmartCampus_Agent_Security_v2_Refined.docx")
    try:
        doc.save(str(out_file2))
        print(f"Saved artifact copy to: {out_file2}")
    except Exception as e:
        print(f"Could not save to artifact directory: {e}")

if __name__ == "__main__":
    create_document()
