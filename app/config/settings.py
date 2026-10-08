import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # llm
    LLM_PROVIDER: str = Field(default="gemini", description="Provider chính: 'gemini' hoặc 'ollama'")
    GEMINI_API_KEY: str = Field(default="", description="API key cho Google Gemini")
    AGENT: str = Field(default="gemini-3.6-flash", description="Model Gemini dùng cho ReAct/Review/Reflect")
    
    # Ollama Local SLM & Embeddings
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Base URL cho Ollama service")
    OLLAMA_MODEL: str = Field(default="qwen2:1.5b", description="Model SLM cho Ollama (vd: qwen2:1.5b, qwen2:0.5b)")
    OLLAMA_EMBEDDING_MODEL: str = Field(default="nomic-embed-text", description="Model embedding chạy trên Ollama")
    OLLAMA_FALLBACK_MODEL: str = Field(default="qwen2:1.5b", description="Model SLM Ollama dùng khi fallback")
    OLLAMA_NUM_CTX: int = Field(default=16384, description="Context window size cho Ollama")

    # db.py (PostgreSQL với pgvector)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://smartcampus:change-this-local-password@localhost:5432/smartcampus",
        description="Database URL kết nối PostgreSQL/pgvector",
    )
    DB_POOL_MIN_SIZE: int = Field(default=2, ge=1)
    DB_POOL_MAX_SIZE: int = Field(default=10, ge=1)

    # EMBEDDING
    VOYAGE_API_KEY: str = Field(default="", description="API key Voyage AI cho search_history")
    EMBEDDING_MODEL: str = Field(default="nomic-embed-text", description="Tên embedding model (nomic-embed-text hoặc voyage-3)")
    EMBEDDING_DIM: int = Field(default=768, description="Số chiều vector (768 với nomic-embed-text, 1024 với voyage-3)")

    # gateway/
    BACKEND_BASE_URL: str = Field(default="http://smartcampus-api:8000", description="Base URL của SmartCampus backend chính")
    GATEWAY_BASE_URL: str = Field(default="http://smartcampus-api:8000/api", description="Base URL kết nối Edge Gateway API")
    BACKEND_SERVICE_TOKEN: str = Field(default="", description="Service token agent dùng để gọi backend")
    USE_MOCK_RAG: bool = Field(default=False, description="Tự động dùng Mock Data cho RAG tools khi backend offline")

    # logging/audit.py
    AUDIT_OUTPUT_DIR: str = Field(default="./output", description="Thư mục ghi file JSON audit mỗi lần evaluate")

    # agent/
    EVALUATE_TIMEOUT_SECONDS: int = Field(default=25, ge=1, description="Timeout tổng cho 1 lần /evaluate")
    ENVIRONMENT_CONTEXT_TIMEOUT_SECONDS: int = Field(default=3, ge=1, description="Timeout cho enrich context với environment")
    ENVIRONMENT_CONTEXT_MAX_ROWS: int = Field(default=50, ge=1, description="Số rows tối đa cho environment context")
    MAX_REACT_STEP: int = Field(default=6, ge=1, description="Số bước Thought/Action tối đa mỗi vòng ReAct")
    MAX_REFLECT_STEP: int = Field(default=3, ge=1, description="Số vòng Review->Reflect->retry tối đa (Tmax)")
    MAX_RAG_CALLS: int = Field(default=5, ge=0, description="Giới hạn cứng số lần gọi RAG tool / request")
    CONFIDENCE_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0, description="Dưới ngưỡng này bắt buộc skip=true")

    # JWT Authentication
    SECRET_KEY: str = Field(default="smartcampus-super-secret-key-change-in-production", description="JWT signing secret key")
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480, ge=1, description="JWT token expiry in minutes")

    # MQTT Broker (WebSocket bridge)
    MQTT_BROKER_HOST: str = Field(default="localhost", description="MQTT broker hostname")
    MQTT_BROKER_PORT: int = Field(default=1883, ge=1, description="MQTT broker port")
    MQTT_USERNAME: str = Field(default="", description="MQTT username (optional)")
    MQTT_PASSWORD: str = Field(default="", description="MQTT password (optional)")
    MQTT_CLIENT_ID: str = Field(default="smartcampus-fastapi-bridge", description="MQTT client identifier")

    @field_validator("BACKEND_BASE_URL")
    @classmethod
    def base_url_no_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


settings = Settings()