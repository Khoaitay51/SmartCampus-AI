-- =============================================================================
-- SmartCampus AI - PostgreSQL pgvector Initialization Script
-- =============================================================================

-- 1. Bật extension pgvector để hỗ trợ lưu trữ và tìm kiếm vector tương đồng
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tạo schema agent_memory riêng biệt dành cho bộ nhớ ngữ cảnh và LTM của AI Agent
CREATE SCHEMA IF NOT EXISTS agent_memory;

-- 3. Cấp quyền đầy đủ cho user ứng dụng
GRANT ALL PRIVILEGES ON SCHEMA agent_memory TO smartcampus;

-- 4. Bảng lưu trữ tri thức (RAG Knowledge Store) hỗ trợ Hybrid Search (FTS + pgvector)
CREATE TABLE IF NOT EXISTS agent_memory.campus_documents (
    id VARCHAR PRIMARY KEY,
    doc_type VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))) STORED,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chỉ mục Full-Text Search (GIN) cho Keyword Search
CREATE INDEX IF NOT EXISTS idx_campus_docs_tsv
ON agent_memory.campus_documents USING gin (tsv);

-- Chỉ mục Semantic Vector (HNSW Cosine) cho Vector Search
CREATE INDEX IF NOT EXISTS idx_campus_docs_embedding
ON agent_memory.campus_documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 5. Bảng lưu trữ Contextual Memory (Telemetry Rollup: Hourly, Daily, Weekly)
CREATE TABLE IF NOT EXISTS agent_memory.contextual_memory_logs (
    id VARCHAR PRIMARY KEY,
    room_id VARCHAR(100) NOT NULL,
    period VARCHAR(20) NOT NULL, -- 'hourly', 'daily', 'weekly'
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    summary_text TEXT NOT NULL,
    metrics_data JSONB DEFAULT '{}'::jsonb,
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_context_mem_embedding
ON agent_memory.contextual_memory_logs USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_context_mem_room_period
ON agent_memory.contextual_memory_logs (room_id, period, start_time DESC);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA agent_memory TO smartcampus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA agent_memory TO smartcampus;


