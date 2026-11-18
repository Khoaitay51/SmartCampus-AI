# Related Work: so sánh với các công trình đã khảo sát

*Nguồn: sheet "My Agentic IOT architecture review" (trang Attack agent 44 bài, trang IOT agent 11 bài; bỏ trùng còn 52 bài). Mọi ô dưới đây dựa trên tóm tắt trong sheet; cần đối chiếu bản gốc trước khi đưa vào bài báo.*

Ký hiệu: ✓ có · ~ một phần · ✗ không · — không áp dụng · ? sheet không nêu.

## 1. Định vị: ba dòng công trình và chỗ đứng của mình

| Dòng công trình | Đại diện | Làm tốt | Chưa có (so với SmartCampus) |
|:--|:--|:--|:--|
| **A. Benchmark tấn công agent** (môi trường số) | InjecAgent, AgentDojo, ASB, EASE, ToolHijacker | ASR, utility under attack, taxonomy tấn công | Thiết bị vật lý, cảm biến thật; tấn công kiểu **bỏ sót** (SUP) |
| **B. Agent IoT / smart home / CPS** | HomeBench, SimuHome, SMH-Bench, SmartBench, Evil-AI, POEF | Môi trường thiết bị, trạng thái vật lý | Phần lớn **không có tấn công**; bài có tấn công chỉ đo hành động gây hại (commission) |
| **C. Phòng thủ** | CaMeL, AgentSentry, Firewall, SkillGuard, CPS-Guard | Giảm ASR, có bài đo chi phí tiện ích | Không bài nào đặt **sàn phản ứng theo cảm biến** cho lỗi bỏ sót |

**SmartCampus nằm ở giao của A và B:** benchmark tấn công trên agent điều khiển thiết bị thật, đo cả BU lẫn ASR, và thêm chiều mà cả hai dòng đều chưa đo: **tấn công khiến agent không phản ứng với nguy hiểm đã đo được (SUP)**.

## 2. Bảng so sánh chính (các bài có tấn công hoặc phòng thủ trên agent)

| Bài | Miền | Thiết bị vật lý | BU | ASR | Taxonomy | **SUP (bỏ sót)** | **Defense** | **Đối chứng cặp** (≈ clean twin) | Chấm không LLM-judge |
|:--|:--|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| *Attack agent thường (môi trường số)* | | | | | | | | | |
| InjecAgent (#17) | Công cụ số (có smart home) | ✗ | ✗ | ✓ | ✓ (DH, DS) | ✗ | ✗ | ✗ | ? |
| AgentDojo (#20) | Workspace, Slack, Travel, Bank | ✗ | ✓ | ✓ | ~ | ✗ | ~ đánh giá có sẵn | ✗ | ✓ |
| AgentAbstain (#23) | 42 sandbox MCP | ✗ | ✓ | — | ✓ 8 kịch bản | ~ *ngược chiều* | ✗ | ✓ cặp T⁺/T⁻ | ? |
| CaMeL (#29) | AgentDojo | ✗ | ✓ | ✓ | — | ✗ | ✓ đề xuất | ✗ | ✓ |
| AgentSentry (#28) | AgentDojo | ✗ | ✓ | ✓ | — | ✗ | ✓ đề xuất | ~ chạy lại phản thực (để phòng thủ) | ? |
| SkillGuard (#44) | AgentDojo | ✗ | ✓ | ✓ | — | ✗ | ✓ đề xuất | ✗ | ? |
| *IoT / CPS agent (thiết bị vật lý, smart home)* | | | | | | | | | |
| Evil-AI (#7) | Smart home, ICS, building… | ✓ servo | ~ | ✓ | ✓ 5 vector | ✗ | ✗ | ✗ | ✗ |
| PromptShield-Home (#19) | Smart home đa phương thức | ~ | ✓ (SCR) | ✓ (UER) | ✓ 6 nhóm | ~ *do từ chối, không do tấn công* | ~ so kiến trúc (oracle) | ✗ | ? |
| POEF (IoT #4) | Robot (Franka, Unitree) | ✓ | ✓ (TSR) | ✓ (BJSR) | ✓ 6 rủi ro | ✗ | ~ prompt + guard model | ✗ | ? |
| CPS-Guard (#4) | PLC/SCADA (proxy) | ~ | ? | ~ | ✓ 3 dạng | ✗ | ✓ đề xuất | ✗ | ? |
| *Ours* | | | | | | | | | |
| **SmartCampus (ours)** | Building management, cảm biến thật | ✓ | ✓ | ✓ | ✓ 4 lớp | **✓** | ✓ Guardrail (6 model) | **✓ clean twin** | ✓ |

**Đọc bảng:**
- **SUP:** trong 52 bài, không bài nào đo tấn công *nhằm khiến agent không phản ứng* với nguy hiểm đã đo. Gần nhất là PromptShield-Home (agent bỏ sót người ngã, nhưng do từ chối quá mức chứ không do tấn công) và AgentAbstain (chiều ngược lại: khi nào agent *không nên* hành động). Mọi benchmark tấn công còn lại đo **commission** (làm điều có hại).
- **Đối chứng cặp:** ý tưởng cặp không mới (AgentAbstain T⁺/T⁻, EpiSEM W⁻/W⁺, EmbSoftOTBench #8 cặp threat/benign). Điểm khác của clean twin là **mục đích**: tách lỗi do tấn công khỏi lỗi do ground truth lệch chính sách. Nên viết là "áp dụng đối chứng cặp để kiểm tra tính hợp lệ của phép đo", không nhận là phát minh.

## 3. Các bài tấn công có nhắc đến defense không? (câu thầy hỏi)

| Mức độ | Bài | Nhận xét |
|:--|:--|:--|
| **Không bàn phòng thủ** | InjecAgent, Evil-AI | Evil-AI chỉ đo khả năng tự chống của model (Defense Rate), không đề xuất cơ chế |
| **Chỉ thảo luận / lý thuyết** | Greshake (#26), Agent Smith (#35), Dark Side (#39), OpenClaw (#40) | Dark Side đề xuất Security Proxy nhưng chưa đo; OpenClaw không có benchmark định lượng |
| **Đánh giá phòng thủ có sẵn** | AgentDojo, ASB, EASE, ToolHijacker, BadChain, BadAgents, AgentPoison, Sleeper Memory, ToolEmu, BEAT, FuncPoison, BALD, POEF | Phòng thủ thử nghiệm thường **thất bại** (FuncPoison ASR vẫn > 84%; ToolHijacker; BadAgents) hoặc **làm hỏng tiện ích** (POEF: SafeRobot prompt làm TSR của GPT-4o giảm 82.67 điểm; BadChain: Shuffle giảm độ chính xác). EASE: prompt phòng thủ có lúc **tăng** ASR |
| **Đề xuất phòng thủ mới và đo** | CPS-Guard, Firewall, AgentSentry, CaMeL, AutoDefense, Owner-Harm (Nous), SkillGuard, RESTRAIN | Phần lớn trên môi trường số; CPS-Guard và RESTRAIN là hai bài phòng thủ cho CPS/IoT |

**Kết luận cho thầy:** bài tấn công thường dừng ở việc *thử* phòng thủ có sẵn, và kết quả lặp lại là: phòng thủ dựa trên prompt không đủ, hoặc an toàn hơn thì mất tiện ích. Đây đúng là chỗ SmartCampus trả lời: **guard không dựa vào LLM, và BU không giảm** (Bảng 4).

## 4. Phòng thủ: hiệu quả và chi phí tiện ích

| Phòng thủ | Bối cảnh | Hiệu quả | Chi phí tiện ích |
|:--|:--|:--|:--|
| CaMeL (#29) | AgentDojo | GPT-4o: 233 → 0 vụ thành công | Hoàn thành tác vụ 84% → 77% |
| AgentSentry (#28) | AgentDojo | ASR 0% | UA 76.1%; từ chối nhầm 2.06–5.15% |
| SkillGuard (#44) | AgentDojo | ASR 0% ở 3 miền; Slack 4.76–14.29% | Giữ 93.21–94.08% năng lực (Travel) |
| SafeRobot prompt (POEF) | Robot | Giảm BJSR | TSR GPT-4o −82.67 điểm |
| CPS-Guard (#4) | CPS proxy, 300 input | Lỗi 60–78% → < 12% | Trễ +10–18%; BU: sheet không nêu |
| **Guardrail (ours)** | SmartCampus, 6 model | ASR 2.8–27.6% → 0.4–4.5% | **BU +2 đến +10 điểm**; báo nhầm 0–3/60 ca (replay) |

## 5. Bài gần nhất cần phân biệt rõ

- **CPS-Guard (#4):** cũng là lớp kiểm định đặt giữa LLM và bộ điều khiển, có *veto* theo ngưỡng vật lý và phát hiện bất thường telemetry. **Khác biệt:** CPS-Guard chặn lệnh nguy hiểm (commission); SensorGuard thêm **floor** cho lỗi bỏ sót (SUP), không đọc text, và được đo BU trên 6 model.
- **Policy-Aware Edge LLM-RAG (#1), Cyber-Physical GraphRAG (#5), Hybrid RAG (#11):** đều có lớp kiểm tra tất định trước khi ra lệnh, nhưng không đặt trong bối cảnh tấn công.
- **RESTRAIN (IoT #6):** phòng thủ trước sự kiện cảm biến **giả mạo** (event spoofing). Đây chính là phần mình để ngoài phạm vi (toàn vẹn cảm biến). Trích bài này để cho thấy hướng đó đã có công trình riêng, hỗ trợ lựa chọn phạm vi của mình.
- **SmartBench (IoT #10):** LLM phát hiện bất thường có FPR tới 78.2%. Dùng để nhấn mạnh vì sao báo động giả là chỉ số phải đo.

## 6. Đoạn related work gợi ý (bản nháp)

> Các benchmark tấn công agent như InjecAgent, AgentDojo và ASB đã chuẩn hoá cách đo ASR và tiện ích khi bị tấn công, nhưng đều trên công cụ số và chỉ xét tấn công khiến agent *làm* điều có hại. Ở mảng agent cho nhà thông minh và hệ thống vật lý, các benchmark như HomeBench, SimuHome và SMH-Bench đánh giá khả năng thực hiện lệnh mà không có kẻ tấn công; các công trình có tấn công vật lý như Evil-AI hay POEF cũng chỉ đo hành động gây hại. Chưa công trình nào trong phạm vi khảo sát đo trường hợp văn bản độc hại khiến agent *không phản ứng* với một nguy hiểm mà cảm biến đã đo được. Về phòng thủ, các bài tấn công thường chỉ thử các biện pháp có sẵn và ghi nhận chúng thất bại hoặc làm giảm tiện ích, như phòng thủ bằng prompt trong FuncPoison và POEF; các phòng thủ mới như CaMeL, AgentSentry hay SkillGuard tập trung vào luồng dữ liệu của agent phần mềm. CPS-Guard gần nhất với hướng của chúng tôi khi kiểm định lệnh theo ngưỡng vật lý, nhưng chỉ chặn hành động nguy hiểm. Công trình này bổ sung (i) lớp tấn công kiểu bỏ sót (SUP), (ii) đối chứng clean twin để xác nhận lỗi do tấn công gây ra, và (iii) một lớp bảo vệ dựa trên cảm biến không đọc văn bản, đảm bảo sàn phản ứng mà không làm giảm tiện ích.

## 7. Lưu ý trước khi đưa vào bài

- Các ô "?" cần tra bản gốc, nhất là cột **Chấm không LLM-judge** và **BU**.
- Một số bài trong sheet ghi "Chưa công bố" hoặc arXiv (#40, #41, #42, #44); khi trích trên tạp chí nên ưu tiên bài đã đăng.
- Câu "không bài nào đo SUP" chỉ đúng **trong 52 bài đã khảo sát**; nên viết đúng như vậy.
