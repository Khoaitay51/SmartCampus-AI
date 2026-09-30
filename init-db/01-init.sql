-- =============================================================================
-- SmartCampus AI - PostgreSQL pgvector Initialization Script
-- =============================================================================

-- 1. Bật extension pgvector để hỗ trợ lưu trữ và tìm kiếm vector tương đồng
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tạo schemas
CREATE SCHEMA IF NOT EXISTS agent_memory;
CREATE SCHEMA IF NOT EXISTS campus;

-- 3. Cấp quyền đầy đủ cho user ứng dụng
GRANT ALL PRIVILEGES ON SCHEMA agent_memory TO smartcampus;
GRANT ALL PRIVILEGES ON SCHEMA campus TO smartcampus;

-- =============================================================================
-- Agent Memory Tables (AI Service)
-- =============================================================================

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

CREATE INDEX IF NOT EXISTS idx_campus_docs_tsv
ON agent_memory.campus_documents USING gin (tsv);

CREATE INDEX IF NOT EXISTS idx_campus_docs_embedding
ON agent_memory.campus_documents USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 5. Bảng lưu trữ Contextual Memory (Telemetry Rollup: Hourly, Daily, Weekly)
CREATE TABLE IF NOT EXISTS agent_memory.contextual_memory_logs (
    id VARCHAR PRIMARY KEY,
    room_id VARCHAR(100) NOT NULL,
    period VARCHAR(20) NOT NULL,
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

-- =============================================================================
-- Campus Tables (RBAC + BMS Management)
-- =============================================================================

-- 6. Users table (RBAC: admin, lecturer, student)
CREATE TABLE IF NOT EXISTS campus.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(20) NOT NULL DEFAULT 'student' CHECK (role IN ('admin', 'lecturer', 'student')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    avatar_url VARCHAR(512),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON campus.users (email);
CREATE INDEX IF NOT EXISTS idx_users_username ON campus.users (username);

-- 7. RFID Cards
CREATE TABLE IF NOT EXISTS campus.rfid_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid VARCHAR(50) UNIQUE NOT NULL,
    user_id UUID REFERENCES campus.users(id) ON DELETE SET NULL,
    is_registered BOOLEAN NOT NULL DEFAULT FALSE,
    registered_at TIMESTAMPTZ,
    last_scanned_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rfid_uid ON campus.rfid_cards (uid);

-- 8. Rooms (FSM 7 states)
CREATE TABLE IF NOT EXISTS campus.rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    building VARCHAR(100),
    floor INTEGER,
    capacity INTEGER DEFAULT 40,
    mode VARCHAR(20) NOT NULL DEFAULT 'SAVING'
        CHECK (mode IN ('SAVING','SELF_STUDY','LECTURE','EXAM','LOCK','SUSPECTED','EMERGENCY')),
    previous_mode VARCHAR(20),
    temperature FLOAT,
    humidity FLOAT,
    co2 FLOAT,
    occupancy INTEGER NOT NULL DEFAULT 0,
    door_locked BOOLEAN NOT NULL DEFAULT TRUE,
    fan_on BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 9. Devices (ESP32 nodes)
CREATE TABLE IF NOT EXISTS campus.devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mac_address VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100),
    device_type VARCHAR(50) DEFAULT 'sensor_node',
    firmware_version VARCHAR(50),
    room_id UUID REFERENCES campus.rooms(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'offline'
        CHECK (status IN ('online','offline','provisioning')),
    last_heartbeat TIMESTAMPTZ,
    ip_address VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devices_mac ON campus.devices (mac_address);

-- 10. Room Sessions
CREATE TABLE IF NOT EXISTS campus.room_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES campus.rooms(id) ON DELETE CASCADE,
    lecturer_id UUID REFERENCES campus.users(id) ON DELETE SET NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'LECTURE',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    checkin_deadline TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_room_active ON campus.room_sessions (room_id, is_active);

-- 11. Attendance Records
CREATE TABLE IF NOT EXISTS campus.attendance_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES campus.room_sessions(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES campus.users(id) ON DELETE CASCADE,
    rfid_uid VARCHAR(50),
    checked_in_at TIMESTAMPTZ DEFAULT NOW(),
    is_late BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'present'
);

CREATE INDEX IF NOT EXISTS idx_attendance_session ON campus.attendance_records (session_id);

-- 12. AI Recommendations (HITL)
CREATE TABLE IF NOT EXISTS campus.ai_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id VARCHAR,
    room_id UUID REFERENCES campus.rooms(id) ON DELETE SET NULL,
    tool_name VARCHAR(100) NOT NULL,
    tool_params JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT,
    confidence FLOAT,
    urgency VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    reviewed_by UUID REFERENCES campus.users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_status ON campus.ai_recommendations (status);

-- =============================================================================
-- Canonical Deterministic Seed Data (FR-DM-02, Sync with Edge & ESP32)
-- =============================================================================
-- 13. Pre-seed default room (Phòng 402) & Corridor
INSERT INTO campus.rooms (id, name, building, floor, capacity, mode, temperature, humidity, co2, occupancy, door_locked, fan_on)
VALUES 
    ('11111111-1111-1111-1111-111111111111', 'Phong Hoc Thong Minh 402', 'A', 4, 40, 'SAVING', 26.5, 60.0, 450.0, 0, TRUE, FALSE),
    ('11111111-1111-1111-1111-111111111110', 'Hanh Lang Tang 4', 'A', 4, 100, 'SAVING', 27.0, 62.0, 420.0, 0, FALSE, FALSE)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    building = EXCLUDED.building,
    floor = EXCLUDED.floor;

-- 14. Pre-seed Users (Admin, Lecturer, Students)
INSERT INTO campus.users (id, username, email, hashed_password, full_name, role, is_active)
VALUES
    ('55555555-5555-5555-5555-555555555555', 'admin_quantri', 'admin@smartcampus.edu.vn', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQmG6W5650n6.b68.7t/m', 'Quan Tri Vien', 'admin', TRUE),
    ('22222222-2222-2222-2222-222222222222', 'gv_nguyenvana', 'nguyenvana@smartcampus.edu.vn', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQmG6W5650n6.b68.7t/m', 'TS. Nguyen Van A', 'lecturer', TRUE),
    ('33333333-3333-3333-3333-333333333333', 'sv_tranthib', 'tranthib@smartcampus.edu.vn', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQmG6W5650n6.b68.7t/m', 'Tran Thi B (SV 1)', 'student', TRUE),
    ('44444444-4444-4444-4444-444444444444', 'sv_lequangc', 'lequangc@smartcampus.edu.vn', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQmG6W5650n6.b68.7t/m', 'Le Quang C (SV 2)', 'student', TRUE)
ON CONFLICT (id) DO UPDATE SET
    username = EXCLUDED.username,
    full_name = EXCLUDED.full_name;

-- 15. Pre-seed RFID Cards
INSERT INTO campus.rfid_cards (uid, user_id, is_registered, registered_at)
VALUES
    ('CARD_ADMIN', '55555555-5555-5555-5555-555555555555', TRUE, NOW()),
    ('CARD_GV_01', '22222222-2222-2222-2222-222222222222', TRUE, NOW()),
    ('CARD_SV_01', '33333333-3333-3333-3333-333333333333', TRUE, NOW()),
    ('CARD_SV_02', '44444444-4444-4444-4444-444444444444', TRUE, NOW()),
    ('1A2B3C4D', '22222222-2222-2222-2222-222222222222', TRUE, NOW()),
    ('A1B2C3D4', '33333333-3333-3333-3333-333333333333', TRUE, NOW()),
    ('5E6F7A8B', '44444444-4444-4444-4444-444444444444', TRUE, NOW())
ON CONFLICT (uid) DO UPDATE SET
    user_id = EXCLUDED.user_id,
    is_registered = TRUE;

-- =============================================================================
-- Grants
-- =============================================================================
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA agent_memory TO smartcampus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA agent_memory TO smartcampus;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA campus TO smartcampus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA campus TO smartcampus;

