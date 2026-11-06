# FREEZE_AGENT.md — Biên bản Đóng Băng Agent Benchmark v2

> **Căn cứ kế hoạch:** `benchmark_v2/BENCHMARK_V2_MASTER_PLAN_FINAL.md` (§1.6, §10.2).  
> **Thời điểm đóng băng:** 27/10/2026.  
> **Cổng duyệt:** Gate G4 — Người dùng đã chính thức phê duyệt nghiệm thu Phase E1 và cấu hình Phase E3.

---

## 1. Thông Tin Nhận Diện & Đóng Băng Phiên Bản

| Thuộc Tính | Giá Trị Đóng Băng | Ghi Chú |
|---|---|---|
| **Git Commit Hash** | `680c4358e4de278960810e0308f4e2d03c1aba06` | Hash commit của repository tại thời điểm chạy |
| **System Prompt Hash (SHA-256)** | `4e68cbd123f24f4b3c685dbb249469c319ed0499aa9d0cf80428f2bb488008e7` | Hash SHA-256 mã nguồn module `app/agent/prompts.py` |
| **Mô hình triển khai chính** | `gemini-3.5-flash-lite` | Provider: `gemini` (Google Gemini API) |
| **Agent Class** | `ReActXenAgent` | Kiến trúc ReAct + Review + Reflect |

---

## 2. Tham Số Cấu Hình Vận Hành

- `AGENT_TEMPERATURE`: `0.0` (Tham số sinh xác định tối đa)
- `AGENT_LLM_MAX_TOKENS`: `2048`
- `EVALUATE_TIMEOUT_SECONDS`: `60.0`
- `MAX_REACT_STEP`: `6`
- `MAX_REFLECT_STEP`: `3`
- `MAX_RAG_CALLS`: `5`
- `CONFIDENCE_THRESHOLD`: `0.35`
- `DISABLE_FALLBACK`: `True` (Tắt hoàn toàn Rule-based Fallback, chế độ LLM-only)
- `BENCHMARK_MODE`: `True` (Tắt LTM write-back, tắt MQTT auto-sync)

---

## 3. Cam Kết Khách Quan Khoa Học

Tuân thủ nghiêm ngặt Quy tắc Master Plan §1.2 điều 2 và điều 12:
- **CẤM** sửa đổi bất kỳ logic prompt, chỉ dẫn an toàn, hoặc cấu trúc điều hướng nào của `ReActXenAgent` trong suốt quá trình chạy thực nghiệm Phase E3.
- Toàn bộ kết quả thu thập được lưu trữ streaming nguyên trạng vào `benchmark_v2/results/<run_id>/raw_runs.jsonl`.
