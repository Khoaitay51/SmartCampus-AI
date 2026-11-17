# Hướng dẫn từng bước: chạy benchmark với `qwen3.5:9b` trên máy thầy (qua AnyDesk)

Mục tiêu: dựng lại môi trường **y hệt máy mình** trên máy thầy (venv, Docker, dữ liệu seed), rồi chạy pilot và k=3 với `qwen3.5:9b` qua Ollama.

> Hướng dẫn này thay thế các đường dẫn cũ trong `HUONG_DAN_CHAY_LOCAL_OLLAMA_K3.md` (bundle DB đã dời sang `framework/env/db_migration_bundle/`; script import đã sửa lại đường dẫn).

**Quy ước:** mỗi bước có khối **Kiểm tra** — chỉ qua bước sau khi kết quả khớp. Chỗ nào khác nhau giữa Linux và Windows thì có hai khối riêng. **Làm theo hệ điều hành của máy thầy** (xem Bước 1).

Biến dùng xuyên suốt:

| Biến | Giá trị |
| :-- | :-- |
| Model | `qwen3.5:9b` |
| Tag | `qwen35_9b` |
| Thư mục kết quả | `models/qwen3_5_9b/` (dấu `:` `.` `-` tự đổi thành `_`) |

---

## PHẦN A. Chuẩn bị TRÊN MÁY BẠN (làm trước khi mở AnyDesk)

### A1. Chốt code và đẩy lên git
Máy thầy sẽ `git clone`, nên mọi thay đổi chưa commit sẽ **không** sang đó. Hiện submodule `AI + Backend` (nhánh `feat/run-multimodel`) còn nhiều file sửa và file mới chưa commit (`app/agent/`, `app/config/settings.py`, `app/safety/`, `framework/defense/`…).

```powershell
cd "D:\SmartCampus\AI + Backend"
git status --short | Select-String -NotMatch "models/|reports/"   # chỉ xem phần code
```
Commit phần code cần thiết rồi push nhánh `feat/run-multimodel` lên `origin`. **Ghi lại hash commit** vào nhật ký run (kết quả phải truy được về đúng code).

> Vì `.gitignore` chặn `.env` và `env/`, hai thứ sau **không** đi theo git, phải chuyển tay ở A2 và A3.

### A2. Export lại dump DB (để dữ liệu khớp trạng thái hiện tại của bạn)
Các lần chạy 16/11 đều ở môi trường **E2** (sau rollup). File dump cũ xuất ngày 11/11 có thể không phải E2, nên xuất lại ngay lúc DB máy bạn đang đúng trạng thái đó. Bật Docker Desktop, đảm bảo `smartcampus-pgvector` và `smartcampus-db` đang chạy:

```powershell
cd "D:\SmartCampus\AI + Backend\benchmarkv2_refined\framework\env\db_migration_bundle"
.\export_db_for_migration.ps1
```
**Kiểm tra:** có 2 file `ai_pgvector.dump` (~3.5 MB), `edge_timescale.dump` (~1.6 MB) với giờ sửa đổi mới.

### A3. Gom file cần mang sang
Nén thành một file `smartcampus_transfer.zip` gồm:
1. Thư mục `db_migration_bundle/` (2 dump + 2 script `.ps1`).
2. `AI + Backend/.env` và `edge/.env` của bạn (chỉ để tham khảo; trên máy thầy bạn sẽ tạo `.env` mới ở Bước 4, **không** copy nguyên vì có API key và đường dẫn khác).

Chuyển file qua AnyDesk (File Transfer) hoặc Google Drive/USB. Đừng đẩy `.env` hay dump lên repo công khai.

---

## PHẦN B. TRÊN MÁY THẦY (qua AnyDesk)

### Bước 1. Xem máy thầy là gì và Ollama chạy ở đâu
Ảnh bạn gửi có dấu nhắc `#`, nên nhiều khả năng đó là **shell root trên Linux** hoặc **bên trong container**. Cần xác định trước, vì nó quyết định cách gọi Ollama.

```bash
uname -a                 # Linux? (Windows: gõ `ver` trong cmd)
whoami                   # root?
docker ps                # có container ollama không?
which ollama             # có cài Ollama thẳng trên máy không?
curl -s http://localhost:11434/api/tags | head -c 400
nvidia-smi               # GPU và VRAM
python3 --version        # cần >= 3.11
docker --version && docker compose version
git --version
```

Đọc kết quả theo bảng:

| Quan sát | Nghĩa là | Việc cần làm |
| :-- | :-- | :-- |
| `curl .../api/tags` trả JSON có `qwen3.5:9b` | Ollama trên host (hoặc container có publish port 11434) chạy tốt | Đi tiếp Bước 2 |
| `docker ps` thấy container ollama **nhưng** `curl` lỗi | Container không publish port | Dừng, cần chạy lại container với `-p 11434:11434` (hỏi lại bạn/thầy trước khi đụng container của thầy) |
| `which ollama` có, `curl` lỗi | Service chưa chạy | `ollama serve &` rồi `curl` lại |
| Không có Docker / Python / git | Thiếu công cụ | Cài trước (xem Bước 2), nếu không có quyền thì dừng và báo thầy |

> Không dùng `docker compose up -d` cho cả thư mục `AI + Backend`: nó bật thêm Ollama thứ hai (xung đột port 11434) và tự pull `qwen2:1.5b`. Ta chỉ bật service `db`.

### Bước 2. Kiểm tra model và bộ nhớ

```bash
ollama --version                # nên >= 0.9
ollama list                     # phải có qwen3.5:9b và nomic-embed-text
ollama pull nomic-embed-text    # nếu thiếu (bắt buộc cho RAG, 768 chiều)
ollama run qwen3.5:9b "Xin chào, trả lời một câu ngắn."   # thoát bằng /bye
ollama ps                       # cột PROCESSOR: nên là "100% GPU"
```
**Kiểm tra:** `ollama list` có tên **đúng** `qwen3.5:9b`. Nếu tên khác (ví dụ `qwen3.5:9b-q4_K_M`), dùng đúng tên đó ở mọi nơi bên dưới.

Về bộ nhớ: bản 9B nặng ~6.6 GB, cộng thêm bộ nhớ đệm KV cho `num_ctx=32768`. Nếu `ollama ps` báo `xx% CPU` (GPU không đủ VRAM), mỗi lượt sẽ rất chậm và dễ timeout. **Đừng tự hạ `OLLAMA_NUM_CTX`** vì sẽ lệch thông số so với các model khác; hãy báo bạn quyết định, rồi ghi rõ thay đổi vào nhật ký.

Cài công cụ còn thiếu (Ubuntu/Debian):
```bash
apt update && apt install -y git python3-venv python3-pip curl
# Docker: https://docs.docker.com/engine/install/ubuntu/
```

### Bước 3. Lấy code (kèm submodule)

**Linux:**
```bash
mkdir -p ~/work && cd ~/work
git clone https://github.com/Khoaitay51/SmartCampus-AI.git "AI + Backend"
cd "AI + Backend"
git checkout feat/run-multimodel
git log --oneline -1             # so với hash đã ghi ở A1
```
**Windows (PowerShell):**
```powershell
mkdir D:\SmartCampus -ErrorAction SilentlyContinue; cd D:\SmartCampus
git clone https://github.com/Khoaitay51/SmartCampus-AI.git "AI + Backend"
cd "AI + Backend"; git checkout feat/run-multimodel; git log --oneline -1
```

Edge Gateway (cần cho `localhost:8000`) nằm ở repo riêng:
```bash
cd ..       # ra thư mục cha của "AI + Backend"
git clone https://github.com/Khoaitay51/SmartCampus-edge.git edge
```
Nếu `git clone` đòi đăng nhập (repo private), **dừng lại**, đăng nhập bằng tài khoản của bạn trên máy thầy rồi xoá thông tin đăng nhập sau khi xong, hoặc chuyển code bằng zip. Đừng nhập mật khẩu trong chat/ghi file.

Giải nén `smartcampus_transfer.zip` (từ A3) rồi chép thư mục `db_migration_bundle/` vào:
`AI + Backend/benchmarkv2_refined/framework/env/db_migration_bundle/`
(ghi đè nếu thư mục đã tồn tại — script `.ps1` trong repo đã có bản sửa).

**Kiểm tra:**
```bash
ls "AI + Backend/benchmarkv2_refined/framework/env/db_migration_bundle"   # thấy 2 file .dump
ls "AI + Backend/benchmark_v2/env"                                       # thấy seed_environment.py
```

### Bước 4. Tạo `.env` (cả hai nơi)

**4.1 `edge/.env`**
```bash
cd edge && cp .env.example .env
```
Giữ nguyên mặc định (`POSTGRES_PORT=5432`, `API_PORT=8000`, user/db `smartcampus`, mật khẩu `change-this-local-password`).

**4.2 `AI + Backend/.env`**
```bash
cd "../AI + Backend" && cp .env.example .env && nano .env
```
Đặt **đúng** các dòng sau (các dòng khác giữ mặc định; không cần API key cloud vì chạy local):

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_FALLBACK_MODEL=qwen3.5:9b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
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

EVALUATE_TIMEOUT_SECONDS=60
MAX_REACT_STEP=6
MAX_REFLECT_STEP=3
MAX_RAG_CALLS=5
CONFIDENCE_THRESHOLD=0.35
```
Hai chỗ dễ sai: `VOYAGE_API_KEY=` phải **để trống** (nếu không, vector lệch 1024 chiều so với 768), và URL phải là `localhost`, không phải `ollama` hay `host.docker.internal`.

> `.env.example` hiện lệch một chút so với `.env` của bạn (ví dụ `CONFIDENCE_THRESHOLD=0.5` thay vì 0.35, `EVALUATE_TIMEOUT_SECONDS=25` thay vì 60). Các giá trị này ảnh hưởng kết quả, nên hãy mở `.env` trên máy bạn, so từng dòng `MAX_*`, `CONFIDENCE_THRESHOLD`, `EVALUATE_TIMEOUT_SECONDS` với khối trên và sửa cho khớp.

### Bước 5. Tạo venv và cài thư viện

**Linux:**
```bash
cd "AI + Backend"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt pytest
python -c "import fastapi, sqlalchemy, asyncpg, httpx, pgvector; print('OK imports')"
```
**Windows:**
```powershell
cd "D:\SmartCampus\AI + Backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # nếu bị chặn: Set-ExecutionPolicy -Scope Process Bypass
pip install --upgrade pip
pip install -r requirements.txt pytest
python -c "import fastapi, sqlalchemy, asyncpg, httpx, pgvector; print('OK imports')"
```
**Kiểm tra:** in `OK imports`. Mỗi lần mở terminal mới phải kích hoạt lại venv.

### Bước 6. Bật Docker: Edge + pgvector (build lại image)

```bash
cd edge
docker compose up -d --build        # TimescaleDB :5432, migrate (alembic), API :8000, MQTT :1883
docker compose ps
curl -s http://localhost:8000/health        # kỳ vọng {"status":"ok"...}

cd "../AI + Backend"
docker compose up -d db                     # CHỈ service db (pgvector :5433)
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
**Kiểm tra:** thấy đủ 4 container ở trạng thái `Up`/`healthy`: `smartcampus-db` (5432), `smartcampus-api` (8000), `smartcampus-mqtt` (1883), `smartcampus-pgvector` (5433).

**Không** bật `smartcampus-ai`, `smartcampus-ollama`, `smartcampus-frontend`: runner chạy Python trực tiếp trên host, và container `ai` có worker rollup có thể ghi đè dữ liệu RAG.

Nếu `migrate` lỗi, xem `docker compose logs migrate`. Nếu API không lên, xem `docker compose logs api`.

### Bước 7. Nạp dữ liệu môi trường (seed) — dùng dump

**Cách 1 (khuyến nghị, giống 100% máy bạn).**

*Windows:* script tự làm toàn bộ.
```powershell
cd "D:\SmartCampus\AI + Backend"
.\benchmarkv2_refined\framework\env\db_migration_bundle\import_db_on_target.ps1
```
*Linux:* chạy tay các lệnh tương đương (dừng API trong lúc nạp):
```bash
cd "AI + Backend"
B=benchmarkv2_refined/framework/env/db_migration_bundle
docker stop smartcampus-api

# pgvector
docker cp $B/ai_pgvector.dump smartcampus-pgvector:/tmp/ai_pgvector.dump
docker exec smartcampus-pgvector psql -U smartcampus -d smartcampus -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS vector;" \
  -c "DROP SCHEMA IF EXISTS agent_memory CASCADE;" \
  -c "DROP SCHEMA IF EXISTS campus CASCADE;"
docker exec smartcampus-pgvector pg_restore -U smartcampus -d smartcampus --no-owner --no-acl /tmp/ai_pgvector.dump
docker exec smartcampus-pgvector rm -f /tmp/ai_pgvector.dump

# TimescaleDB
docker cp $B/edge_timescale.dump smartcampus-db:/tmp/edge_timescale.dump
docker exec smartcampus-db psql -U smartcampus -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='smartcampus' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS smartcampus;" \
  -c "CREATE DATABASE smartcampus OWNER smartcampus;"
docker exec smartcampus-db psql -U smartcampus -d smartcampus -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" -c "SELECT timescaledb_pre_restore();"
docker exec smartcampus-db pg_restore -U smartcampus -d smartcampus --no-owner --no-acl -Fc /tmp/edge_timescale.dump
docker exec smartcampus-db psql -U smartcampus -d smartcampus -v ON_ERROR_STOP=1 -c "SELECT timescaledb_post_restore();"
docker exec smartcampus-db rm -f /tmp/edge_timescale.dump

docker start smartcampus-api && sleep 5

# Xác minh theo manifest SHA-256
export PYTHONIOENCODING=utf-8
export BENCHMARK_PGVECTOR_URL="postgresql://smartcampus:change-this-local-password@localhost:5433/smartcampus"
export BENCHMARK_TIMESCALE_URL="postgresql://smartcampus:change-this-local-password@localhost:5432/smartcampus"
python benchmark_v2/env/seed_environment.py --verify
```
(`pg_restore` có thể in vài cảnh báo vô hại; chỉ cần không có `ERROR` làm dừng.)

**Kiểm tra:** thấy dòng `TOÀN BỘ 5 PHÒNG BENCHMARK KHỚP 100% VỚI MANIFEST!` (Windows: thêm `[OK] CACH 1 HOAN TAT`). Sau đó:
```bash
curl -s http://localhost:8000/health
```

**Cách 2 (dự phòng nếu không có dump)** — phải đúng thứ tự, với venv đang bật và 2 biến `BENCHMARK_*` ở trên đã export:
```bash
python -m app.script.ingest                      # tạo bảng ORM + nạp 4 file SOP (BẮT BUỘC chạy trước)
python benchmark_v2/env/seed_environment.py      # seed 5 phòng
(cd ../edge && docker compose restart api)
python benchmark_v2/env/seed_environment.py --verify
```
Lưu ý: Cách 2 dựng lại trạng thái "seed" (E1), **không** phải E2 sau rollup, nên có thể không khớp với các model khác. Ưu tiên Cách 1.

### Bước 8. Kiểm tra code offline

```bash
export PYTHONIOENCODING=utf-8
python -m unittest benchmarkv2_refined/framework/attack_advanced/tests/test_evaluator_advanced.py
python -m pytest benchmarkv2_refined/framework/benign/tests/test_evaluator_v2.py -q
```
**Kiểm tra:** cả hai pass (chạy ~1 giây, không gọi LLM).

### Bước 9. Pilot 5 ca (để thử tốc độ, định dạng và môi trường)

```bash
python -m benchmarkv2_refined.framework.attack_advanced.runner.run_advanced_attack \
  --run-id qwen35_9b_pilot --suite attack_advanced_pilot --limit 5 \
  --provider ollama --model qwen3.5:9b --timeout 180
```
(Windows: thay `\` cuối dòng bằng dấu backtick `` ` ``, hoặc gộp thành một dòng.)

Quan sát lúc chạy: mở terminal thứ hai gõ `ollama ps` và `nvidia-smi` để xem GPU có đang dùng; ghi lại **thời gian mỗi ca**.

Kiểm tra kết quả:
```bash
F=benchmarkv2_refined/models/qwen3_5_9b/attack_advanced_pilot/qwen35_9b_pilot/raw_runs.jsonl
wc -l $F
grep -c '"run_status": *"OK"' $F          # kỳ vọng 5
grep -c '"is_fallback": *true' $F         # kỳ vọng 0
grep -c 'HÀNG NGÀY' $F                    # kỳ vọng 5 (môi trường E2)
```
Cách đọc:
- `run_status` không phải `OK` hoặc `is_fallback: true` nhiều: model xuất sai định dạng hoặc timeout; xem `Bước 12`.
- Có "Báo cáo vi khí hậu và ghi chú phòng…" thay vì `HÀNG NGÀY`: môi trường đang là **E1**. **Dừng lại**, báo bạn (xem `GROUND_TRUTH_ATTACK.md` §10, cần dump E2 mới).
- Một ca mất hơn ~3 phút: tính ra k=3 sẽ rất lâu; báo bạn trước khi chạy tiếp.

> Nếu đường dẫn thư mục kết quả khác (runner đặt tên suite khác), tìm bằng `find benchmarkv2_refined/models/qwen3_5_9b -name raw_runs.jsonl`.

### Bước 10. Chạy trọn bộ k=3

Trước tiên tắt chế độ Sleep trên máy thầy (Windows: Power & Sleep → Never; Linux: `systemctl mask sleep.target suspend.target`), và chạy trong `tmux`/`screen` (Linux) để đóng AnyDesk không làm dừng tiến trình:
```bash
tmux new -s qwen        # thoát khỏi tmux mà không dừng: Ctrl+b rồi d ; vào lại: tmux attach -t qwen
```

Chạy lần lượt (mỗi lệnh phải xong và thành công mới sang lệnh sau):

```bash
cd "AI + Backend" && source .venv/bin/activate
export PYTHONIOENCODING=utf-8
MODEL="qwen3.5:9b"; TAG="qwen35_9b"; TIMEOUT=180
SLUG=qwen3_5_9b

# 1) Benign k=3 (100 ca/lượt)
python benchmarkv2_refined/framework/benign/run_benign_k3_pipeline.py \
  --provider ollama --model "$MODEL" --tag "$TAG" --config with_conf_reflect --timeout $TIMEOUT \
  2>&1 | tee "log_${TAG}_benign_k3.txt"

# 2) Advanced attack k=3 (285 ca/lượt) — cần file tổng kết benign ở bước 1
python benchmarkv2_refined/framework/attack_advanced/run_advanced_attack_k3_pipeline.py \
  --provider ollama --model "$MODEL" --tag "$TAG" --timeout $TIMEOUT \
  --benign-summary "benchmarkv2_refined/models/$SLUG/benign/k3_benign_summary_${TAG}_with_conf_reflect.json" \
  2>&1 | tee "log_${TAG}_adv_k3.txt"

# 3) Clean-twin SUP k=3 (100 ca/lượt)
python benchmarkv2_refined/framework/attack_advanced/run_clean_twin_k3_pipeline.py \
  --provider ollama --model "$MODEL" --tag "$TAG" --timeout $TIMEOUT \
  2>&1 | tee "log_${TAG}_clean_twin_sup_k3.txt"
```
Về thứ tự: benign chạy **trước** vì lệnh 2 cần BU từ file summary của nó. Nếu bước 1 xong mà file summary tên khác, kiểm tra bằng `ls benchmarkv2_refined/models/$SLUG/benign/`.

Gợi ý nếu chỉ còn ít thời gian: chạy bước 1 rồi chạy **một vòng** (r1) của bước 2 qua runner đơn thay vì k=3, và báo bạn quyết định. Đừng tự bỏ bước nào.

Theo dõi tiến độ: `tail -f log_qwen35_9b_adv_k3.txt`.

### Bước 11. Lấy kết quả mang về

| Chỉ số | File |
| :-- | :-- |
| BU + Action Compliance, Class Acc | `models/qwen3_5_9b/benign/K3_BENIGN_REPORT_qwen35_9b_with_conf_reflect.md` |
| ASR, SUP, DH-A, DH-S, DS, UA, MHR, FDR | `models/qwen3_5_9b/attack_advanced/K3_ATTACK_SYNTHESIS_qwen35_9b_adv.md` |
| SUP nhánh A vs P vs Z | `models/qwen3_5_9b/clean_twin_sup/out_clean_twin_sup_qwen35_9b/clean_twin_sup_report.md` |

(đường dẫn tính từ `AI + Backend/benchmarkv2_refined/`). Nén cả thư mục `benchmarkv2_refined/models/qwen3_5_9b/` cùng 3 file `log_*.txt`, chuyển về máy bạn bằng AnyDesk File Transfer. Chấm lại hoàn toàn trên máy bạn từ `raw_runs.jsonl` bằng evaluator chuẩn (mục "Chấm điểm theo ground truth chuẩn" trong `benchmarkv2_refined/README.md`).

### Bước 12. Xử lý lỗi thường gặp

| Triệu chứng | Nguyên nhân và cách sửa |
| :-- | :-- |
| Bị ngắt giữa chừng (mất AnyDesk, tắt terminal) | Chạy lại **đúng lệnh cũ** (cùng `MODEL`, `TAG`): runner resume từ `raw_runs.jsonl`, không mất dữ liệu |
| `relation "agent_memory.environment_snapshots" does not exist` | Dùng Cách 2 mà chưa chạy `python -m app.script.ingest` trước. Chạy nó rồi seed lại. Với Cách 1 thì kiểm tra bước `pg_restore` có lỗi không |
| `expected 1024 dimensions, not 768` | `.env` thiếu `EMBEDDING_DIM=768` / `EMBEDDING_MODEL=nomic-embed-text` hoặc `VOYAGE_API_KEY` chưa để trống |
| Seed/verify sai cổng 5432/5433 | Chưa export 2 biến `BENCHMARK_PGVECTOR_URL` (`:5433`) và `BENCHMARK_TIMESCALE_URL` (`:5432`) |
| `Connection refused localhost:11434` | Ollama chưa chạy hoặc ở container không publish port (xem Bước 1) |
| Port 11434 / 8000 / 5432 bị chiếm | `docker ps` xem container lạ; `ss -ltnp \| grep 5432` (Linux) / `netstat -ano \| findstr 5432` (Windows). Không tắt container của thầy khi chưa hỏi |
| Rất nhiều `is_fallback: true`, JSON/ReAct sai định dạng | Qwen3.5 có thể đang "suy nghĩ" (`<think>`). Code đã tự tắt `think` cho tên có `qwen3` và tự strip `<think>`; nếu vẫn lỗi, thử thêm `OLLAMA_THINK=false` vào `.env`, ghi lại, chạy pilot lại |
| Timeout liên tục | `ollama ps` xem model có chạy trên CPU không; nạp trước model: `ollama run qwen3.5:9b ""` rồi chạy lại. Tăng `--timeout` chỉ khi đã báo bạn (lệch thông số) |
| `docker compose up` báo thiếu `.env` | `cp edge/.env.example edge/.env` |
| Dừng ngang vì `STOP_AFTER_R2.flag` | File này (nếu có) làm run có `r3` dừng; trong repo hiện không còn file này, nhưng nếu xuất hiện thì hỏi bạn trước khi xoá |

### Bước 13. Dọn dẹp sau khi xong
```bash
cd "AI + Backend" && docker compose stop db
cd ../edge && docker compose stop
```
`stop` (không `down -v`) để giữ dữ liệu. **Không** chạy `docker system prune` hay xoá volume trên máy thầy. Nếu muốn xoá hẳn môi trường bạn đã dựng, hỏi thầy trước.

---

## Checklist nhanh (in ra hoặc để cạnh màn hình)

- [ ] A1 đã push code, ghi hash commit
- [ ] A2 đã export dump mới; A3 đã chuyển zip
- [ ] B1 xác định OS và chỗ chạy Ollama; `curl :11434/api/tags` có `qwen3.5:9b`
- [ ] B2 `ollama ps` cho thấy chạy GPU
- [ ] B3 đã clone code và edge; dump đã nằm đúng thư mục
- [ ] B4 hai file `.env` đúng, `VOYAGE_API_KEY` để trống
- [ ] B5 venv + `pip install` xong, `OK imports`
- [ ] B6 đủ 4 container, `/health` ok
- [ ] B7 `KHỚP 100% VỚI MANIFEST`
- [ ] B8 test offline pass
- [ ] B9 pilot: 5 OK, 0 fallback, 5 dòng `HÀNG NGÀY`
- [ ] B10 chạy benign → attack → clean-twin trong tmux
- [ ] B11 kéo kết quả và log về máy bạn
