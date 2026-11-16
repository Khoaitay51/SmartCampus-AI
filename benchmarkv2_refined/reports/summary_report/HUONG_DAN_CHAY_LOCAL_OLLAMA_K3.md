# Hướng Dẫn Setup & Chạy Benchmark $k=3$ Với Model Local (Ollama / Qwen) Trên Máy Thầy

Tất cả các chỗ hardcode model cũ, cấu hình context/determinism, và xử lý output cho Ollama/Qwen trong pipeline $k=3$ **đã được cập nhật sẵn** trong repo (vẫn giữ nguyên 100% logic & parity khi chạy Gemini):
- [`app/config/settings.py`](../../../app/config/settings.py) & [`app/llm/ollama.py`](../../../app/llm/ollama.py): mặc định `OLLAMA_NUM_CTX = 32768`, `temperature = 0.0`, prompt trung tính khớp với `GeminiLLMClient`, và tự truyền `"think": False` cho họ `qwen3*` (có fallback tự động nếu Ollama bản cũ trả HTTP 400).
- [`app/agent/output_parser.py`](../../../app/agent/output_parser.py): tự strip `<think>...</think>` và trích JSON linh hoạt cho bước Review để giảm lỗi format ở model local.
- [`benchmarkv2_refined/framework/benign/run_benign_k3_pipeline.py`](../../framework/benign/run_benign_k3_pipeline.py): chạy $k=3$ cho `run_benign.py` + `evaluate_benign_v2.py` và tổng hợp **BU** (`ba_overall`) cùng các chỉ số Benign V2.
- [`benchmarkv2_refined/framework/attack_advanced/run_advanced_attack_k3_pipeline.py`](../../framework/attack_advanced/run_advanced_attack_k3_pipeline.py): chạy $k=3$ cho `run_advanced_attack.py` + [`synthesize_attack_k3.py`](../../framework/attack_advanced/synthesize_attack_k3.py) xuất **ASR, ASR-any, ASR-all, SUP, DH-A, DH-S, DS, UA, $\Delta U$, MHR, FDR, Track B**.
- [`benchmarkv2_refined/framework/attack_advanced/run_clean_twin_k3_pipeline.py`](../../framework/attack_advanced/run_clean_twin_k3_pipeline.py): chạy $k=3$ Clean Twin SUP + [`clean_twin_sup.py`](../../framework/attack_advanced/analysis/clean_twin_sup.py) đối chứng **nhánh A vs P vs Z** cho **SUP**.

---

## Bước 1: Kiểm tra Ollama version, model & Python environment trên máy thầy

Mở PowerShell mới trên máy thầy và chạy tuần tự:

```powershell
# 1) Kiểm tra phiên bản Ollama (khuyên dùng >= 0.9 để hỗ trợ native `"think": false` cho qwen3;
#    bản cũ hơn vẫn chạy được nhờ fallback HTTP 400 + strip <think>)
ollama --version

# 2) Xem danh sách model đã có sẵn trên máy thầy (chú ý ghi lại đúng tên model, vd: qwen2.5:7b, qwen3:8b)
ollama list

# 3) Kiểm tra xem Ollama server đang chạy và đang nạp model nào trên GPU/RAM chưa
ollama ps
Invoke-RestMethod http://localhost:11434/api/tags | Select-Object -ExpandProperty models | Select-Object name

# 4) BẮT BUỘC: Đảm bảo đã có model embedding `nomic-embed-text` (768-dim) cho Live RAG & seed
ollama pull nomic-embed-text
```

> Nếu máy thầy chưa kích hoạt virtualenv Python cho `AI + Backend`, tạo/kích hoạt `.venv` và cài dependencies:
> ```powershell
> cd "D:\SmartCampus\AI + Backend"
> python -m venv .venv
> .\.venv\Scripts\Activate.ps1
> pip install -r requirements.txt
> pip install pytest
> ```

---

## Bước 2: Tạo & kiểm tra file `.env` (CHO CẢ `edge` và `AI + Backend`)

> **Quan trọng:** File `.env` bị gitignore nên máy mới clone/copy code sẽ **chưa có** nếu bạn chưa tạo. Thiếu `edge/.env` sẽ làm `docker compose up -d` lỗi ngay.

### 2.1. Tạo `edge/.env`
```powershell
cd "D:\SmartCampus\edge"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
Kiểm tra nhanh trong `edge/.env` giữ đúng mặc định:
- `POSTGRES_PORT=5432`
- `API_PORT=8000`
- `POSTGRES_USER=smartcampus`, `POSTGRES_PASSWORD=change-this-local-password`, `POSTGRES_DB=smartcampus`

### 2.2. Tạo và chỉnh `AI + Backend/.env`
```powershell
cd "D:\SmartCampus\AI + Backend"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
Mở `D:\SmartCampus\AI + Backend\.env` (ví dụ `notepad .env`) và kiểm tra/chỉnh **đúng các dòng sau** để chạy Python trên host Windows kết nối tới Ollama host + Docker DBs:

```env
LLM_PROVIDER=ollama

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b          # <-- đổi theo đúng tên trong `ollama list`
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_FALLBACK_MODEL=qwen2.5:7b # <-- đổi theo model dự phòng trong `ollama list`
OLLAMA_NUM_CTX=32768

POSTGRES_DB=smartcampus
POSTGRES_USER=smartcampus
POSTGRES_PASSWORD=change-this-local-password
POSTGRES_PORT=5433
DATABASE_URL=postgresql+asyncpg://smartcampus:change-this-local-password@localhost:5433/smartcampus

EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIM=768
VOYAGE_API_KEY=

BACKEND_BASE_URL=http://localhost:8000
GATEWAY_BASE_URL=http://localhost:8000/api
USE_MOCK_RAG=false
```

> **Lưu ý kiểm tra kỹ:**
> - `VOYAGE_API_KEY=` phải **để trống** để agent dùng local `nomic-embed-text` (`768` chiều), không bị lệch `1024` chiều.
> - Nếu bạn copy `.env` từ máy cũ sang có `http://ollama:11434` hay `http://host.docker.internal:8000`, hãy sửa thành `http://localhost:...` để Python chạy trên Windows host gọi thẳng không bị chậm/lỗi DNS.

---

## Bước 3: Bật Docker Edge (`:8000`, `:5432`) & pgvector (`:5433`)

```powershell
# 1) Bật Edge stack (TimescaleDB :5432, Alembic migrate, Edge API :8000, Mosquitto :1883)
cd "D:\SmartCampus\edge"
docker compose up -d

# Chờ vài giây cho migrate chạy xong, kiểm tra Edge API đã lên OK:
Invoke-RestMethod http://localhost:8000/health
# Kỳ vọng: status = ok

# 2) Bật CHỈ service `db` (pgvector :5433) trong AI + Backend
#    KHÔNG chạy `docker compose up -d` toàn bộ để tránh bật service `ollama` trong Docker đụng port 11434!
cd "D:\SmartCampus\AI + Backend"
docker compose up -d db

# 3) Kiểm tra lại 4 container đang chạy khỏe:
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
Cần thấy đủ 4 container: `smartcampus-db` (`5432`), `smartcampus-api` (`8000`), `smartcampus-mqtt` (`1883`), `smartcampus-pgvector` (`5433`).

---

## Bước 4: Nạp dữ liệu môi trường thật cho Live RAG (Chọn 1 trong 2 cách)

Ở giai đoạn chuẩn bị dữ liệu trên máy thầy, bạn có **2 cách song song** (cả 2 đều đã chuẩn bị sẵn đầy đủ script/tài nguyên, khi lên máy thầy bạn chọn cách nào tiện & phù hợp hơn thì chạy cách đó):

| Tiêu chí | **Cách 1: Import Bundle đã export sẵn** (`db_migration_bundle/`) | **Cách 2: Tái tạo sạch bằng script repo** |
| :--- | :--- | :--- |
| **Độ giống dữ liệu máy bạn** | **100% y hệt từng dòng** (2,287 dòng `environment`, 26,283 `raw_summarizer`, 24 `campus_documents`, 826 `contextual_memory_logs`) | Chuẩn theo `env_spec.json` (5 phòng benchmark: 2,165 dòng `environment`, 5 `raw_summarizer`, 5 `contextual_memory_logs`, 4 file SOP) |
| **Phụ thuộc khi nạp** | Chỉ cần Docker DBs đang chạy + copy thư mục `db_migration_bundle` (~5 MB) | Cần Ollama đang chạy & đã pull `nomic-embed-text` + đặt đúng URL/port `5433`/`5432` |
| **Khuyến nghị** | Nhanh nhất & đồng nhất tuyệt đối nếu bạn mang/gửi kèm thư mục `db_migration_bundle` | Dùng khi không mang/copy file dump và muốn tạo mới hoàn toàn trên máy thầy |

---

### Lựa chọn 4A — Cách 1: Nạp từ `db_migration_bundle` đã export sẵn (1 lệnh)

Thư mục [`benchmarkv2_refined/db_migration_bundle/`](db_migration_bundle/) trên máy bạn đã được export & kiểm chứng sẵn gồm:
- `ai_pgvector.dump` (~3.5 MB)
- `edge_timescale.dump` (~1.6 MB)
- [`import_db_on_target.ps1`](db_migration_bundle/import_db_on_target.ps1) (tự tạm dừng Edge API, nạp sạch `pgvector` + `TimescaleDB`, khởi động lại Edge API, kiểm tra số dòng và chạy `seed_environment.py --verify`)
- [`export_db_for_migration.ps1`](db_migration_bundle/export_db_for_migration.ps1) (dùng khi muốn export lại bộ dump mới từ máy bạn)

Copy thư mục `db_migration_bundle` sang đúng vị trí `D:\SmartCampus\AI + Backend\benchmarkv2_refined\db_migration_bundle\` trên máy thầy (qua AnyDesk File Transfer hoặc Git/USB), rồi chạy:

```powershell
cd "D:\SmartCampus\AI + Backend"
.\benchmarkv2_refined\db_migration_bundle\import_db_on_target.ps1
```

> Script mặc định nối `smartcampus-pgvector` (`5433`), `smartcampus-db` (`5432`), `smartcampus-api`, và tự động chạy `seed_environment.py --verify`. Thấy dòng `[OK] CACH 1 HOAN TAT` và `TOÀN BỘ 5 PHÒNG BENCHMARK KHỚP 100% VỚI MANIFEST!` là xong, chuyển thẳng sang **Bước 5**.

---

### Lựa chọn 4B — Cách 2: Tái tạo bằng script chuẩn trong repo (`ingest.py` + `seed_environment.py`)

> **CỰC KỲ QUAN TRỌNG — Phải chạy ĐÚNG THỨ TỰ dưới đây:**
> 1. Trong `benchmark_v2/env/seed_environment.py`, port mặc định fallback đang bị ngược (`5432` vs `5433`), nên **bắt buộc** export `BENCHMARK_PGVECTOR_URL` (`:5433`) và `BENCHMARK_TIMESCALE_URL` (`:5432`).
> 2. `init-db/01-init.sql` chưa tự tạo sẵn một số bảng `agent_memory.*` (như `environment_snapshots`), còn `python -m app.script.ingest` sẽ gọi `init_db()` để tạo đủ toàn bộ bảng ORM và nạp 4 file SOP (`campus_knowledge/sop_01..sop_04.md`). Do đó **BẮT BUỘC chạy `python -m app.script.ingest` TRƯỚC `seed_environment.py`**.

Chạy lần lượt trong PowerShell (đang kích hoạt `.venv`):

```powershell
cd "D:\SmartCampus\AI + Backend"
$env:PYTHONIOENCODING = "utf-8"
$env:BENCHMARK_PGVECTOR_URL  = "postgresql://smartcampus:change-this-local-password@localhost:5433/smartcampus"
$env:BENCHMARK_TIMESCALE_URL = "postgresql://smartcampus:change-this-local-password@localhost:5432/smartcampus"

# 1) Khởi tạo toàn bộ bảng ORM (init_db) + ingest 4 file SOP vào pgvector (:5433)
python -m app.script.ingest

# 2) Seed 5 phòng benchmark (2165 dòng telemetry TimescaleDB :5432 + contextual memory pgvector :5433)
python benchmark_v2/env/seed_environment.py

# 3) Restart Edge API để làm mới kết nối DB
cd "D:\SmartCampus\edge"
docker compose restart api
Start-Sleep -Seconds 3
Invoke-RestMethod http://localhost:8000/health

# 4) Xác minh toàn vẹn dữ liệu 5 phòng khớp SHA-256 manifest
cd "D:\SmartCampus\AI + Backend"
python benchmark_v2/env/seed_environment.py --verify
```

Thấy log báo **`TOÀN BỘ 5 PHÒNG BENCHMARK KHỚP 100% VỚI MANIFEST!`** là dữ liệu môi trường thật (`USE_MOCK_RAG=false`) đã sẵn sàng cho Bước 5.

---

## Bước 5: Kiểm tra nhanh code & chạy Pilot 5 ca

```powershell
cd "D:\SmartCampus\AI + Backend"
$env:PYTHONIOENCODING = "utf-8"

# 1) Kiểm tra unit test evaluator (chạy offline ~1s)
python -m unittest benchmarkv2_refined/framework/attack_advanced/tests/test_evaluator_advanced.py
python -m pytest benchmarkv2_refined/framework/benign/tests/test_evaluator_v2.py -q

# 2) Khai báo biến model (CHỈ SỬA 2 DÒNG $MODEL và $TAG theo `ollama list`)
$MODEL   = "qwen2.5:7b"   # Tên chính xác trong `ollama list`
$TAG     = "qwen25_7b"    # Tên ngắn không chứa ':' để đặt tên folder kết quả
$TIMEOUT = 180

# 3) Chạy thử 5 ca Advanced Attack để kiểm tra tốc độ, format & Live RAG
python -m benchmarkv2_refined.framework.attack_advanced.runner.run_advanced_attack `
  --run-id "${TAG}_pilot" `
  --limit 5 `
  --provider ollama `
  --model $MODEL `
  --timeout $TIMEOUT
```

Mở nhanh `benchmarkv2_refined\models\<model_slug>\attack_advanced\${TAG}_pilot\raw_runs.jsonl` kiểm tra:
- `run_status` là `"OK"`
- `"is_fallback": false`
- Không có lỗi kết nối `localhost:8000`, `localhost:5433`, hoặc `localhost:11434`.

---

## Bước 6: Chạy trọn bộ $k=3$ (Benign $\rightarrow$ Advanced Attack $\rightarrow$ Clean Twin SUP)

### 6.1. Từng lệnh riêng (để hiểu rõ file chạy)
1. **`run_benign` ($k=3$, 100 ca/lượt)** — file chạy: `benchmarkv2_refined/framework/benign/run_benign_k3_pipeline.py`
   ```powershell
   python benchmarkv2_refined/framework/benign/run_benign_k3_pipeline.py `
     --provider ollama --model $MODEL --tag $TAG --config with_conf_reflect --timeout $TIMEOUT
   ```
2. **`run_advanced_attack` ($k=3$, 285 ca/lượt)** — file chạy: `benchmarkv2_refined/framework/attack_advanced/run_advanced_attack_k3_pipeline.py`
   ```powershell
   python benchmarkv2_refined/framework/attack_advanced/run_advanced_attack_k3_pipeline.py `
     --provider ollama --model $MODEL --tag $TAG --timeout $TIMEOUT `
     --benign-summary "benchmarkv2_refined/models/<model_slug>/benign/k3_benign_summary_${TAG}_with_conf_reflect.json"
   ```
3. **`clean_twin_sup` ($k=3$, 100 ca/lượt)** — file chạy: `benchmarkv2_refined/framework/attack_advanced/run_clean_twin_k3_pipeline.py`
   ```powershell
   python benchmarkv2_refined/framework/attack_advanced/run_clean_twin_k3_pipeline.py `
     --provider ollama --model $MODEL --tag $TAG --timeout $TIMEOUT
   ```

### 6.2. Lệnh chạy gộp 1 lèo (treo máy chạy hết & tự ghi log)

```powershell
cd "D:\SmartCampus\AI + Backend"
$env:PYTHONIOENCODING = "utf-8"

# === SỬA TÊN MODEL VÀ TAG THEO `ollama list` TRÊN MÁY THẦY ===
$MODEL   = "qwen2.5:7b"
$TAG     = "qwen25_7b"
$TIMEOUT = 180

$BENIGN_SUM = "benchmarkv2_refined/models/<model_slug>/benign/k3_benign_summary_${TAG}_with_conf_reflect.json"

python benchmarkv2_refined/framework/benign/run_benign_k3_pipeline.py `
  --provider ollama --model $MODEL --tag $TAG --config with_conf_reflect --timeout $TIMEOUT `
  | Tee-Object -FilePath "log_${TAG}_benign_k3.txt"

if ($LASTEXITCODE -ne 0) { throw "Benign k=3 failed!" }

python benchmarkv2_refined/framework/attack_advanced/run_advanced_attack_k3_pipeline.py `
  --provider ollama --model $MODEL --tag $TAG --timeout $TIMEOUT --benign-summary $BENIGN_SUM `
  | Tee-Object -FilePath "log_${TAG}_adv_k3.txt"

if ($LASTEXITCODE -ne 0) { throw "Advanced Attack k=3 failed!" }

python benchmarkv2_refined/framework/attack_advanced/run_clean_twin_k3_pipeline.py `
  --provider ollama --model $MODEL --tag $TAG --timeout $TIMEOUT `
  | Tee-Object -FilePath "log_${TAG}_clean_twin_sup_k3.txt"
```

### Bảng file kết quả cần lấy sau khi chạy xong

| Chỉ số cần lấy | File output chứa số liệu |
| :--- | :--- |
| **BU** (`ba_overall`) + Action Compliance, Class Acc, Violations | `benchmarkv2_refined/models/<model_slug>/benign/K3_BENIGN_REPORT_<TAG>_with_conf_reflect.md` |
| **ASR, ASR-any, ASR-all, SUP, DH-A, DH-S, DS, UA, $\Delta U$, MHR, FDR, Track B** | `benchmarkv2_refined/models/<model_slug>/attack_advanced/K3_ATTACK_SYNTHESIS_<TAG>_adv.md` |
| **SUP đối chứng (A vs P vs Z)** | `benchmarkv2_refined/models/<model_slug>/clean_twin_sup/out_clean_twin_sup_<TAG>/clean_twin_sup_report.md` |

---

## Bước 7: Lưu ý treo máy & xử lý nhanh các lỗi thường gặp

1. **Tắt Sleep trên Windows** (chọn `Never` khi cắm nguồn) trước khi treo máy chạy $k=3$.
2. **Nếu bị ngắt giữa chừng:** chạy lại đúng lệnh bị ngắt với **cùng `$MODEL` và `$TAG`**, runner tự đọc `raw_runs.jsonl` và chạy nối tiếp phần còn thiếu (không mất kết quả đã chạy).
3. **Chỉ tổng hợp lại báo cáo không gọi LLM:** thêm cờ `--synthesize-only`.
4. **Lỗi hay gặp & cách sửa ngay:**
   - `relation "agent_memory.environment_snapshots" does not exist`: do chạy `seed_environment.py` trước `ingest.py` $\rightarrow$ chạy `python -m app.script.ingest` trước, rồi chạy lại `seed_environment.py`.
   - `expected 1024 dimensions, not 768`: kiểm tra `AI + Backend/.env` phải có `EMBEDDING_DIM=768`, `EMBEDDING_MODEL=nomic-embed-text`, và `VOYAGE_API_KEY=` để trống.
   - Sai port `5432` / `5433` khi seed hoặc verify: kiểm tra đã set `$env:BENCHMARK_PGVECTOR_URL` (`:5433`) và `$env:BENCHMARK_TIMESCALE_URL` (`:5432`).
   - Đụng port `11434`: đảm bảo trong `AI + Backend` chỉ chạy `docker compose up -d db`, không bật container `ollama`.
   - Edge `docker compose up -d` báo thiếu `.env`: copy `edge/.env.example` thành `edge/.env`.
