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

    # llm.py
    GEMINI_API_KEY: str = Field(default="", description="API key cho Google Gemini")
    AGENT: str = Field(default="gemini-2.5-flash", description="Model Gemini dùng cho ReAct/Review/Reflect")

    # db.py
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/smartcampus",
        description="Database URL kết nối PostgreSQL/pgvector",
    )
    DB_POOL_MIN_SIZE: int = Field(default=2, ge=1)
    DB_POOL_MAX_SIZE: int = Field(default=10, ge=1)

    # EMBEDDING
    VOYAGE_API_KEY: str = Field(default="", description="API key Voyage AI cho search_history")
    EMBEDDING_MODEL: str = Field(default="voyage-3")
    EMBEDDING_DIM: int = Field(default=1024, description="Phải khớp VECTOR(n) trong sql/schema.sql")

    # gateway/
    BACKEND_BASE_URL: str = Field(default="http://localhost:8000/api", description="Base URL của SmartCampus backend chính")
    GATEWAY_BASE_URL: str = Field(default="http://localhost:8000/api", description="Base URL kết nối Edge Gateway API")
    BACKEND_SERVICE_TOKEN: str = Field(default="", description="Service token agent dùng để gọi backend")
    USE_MOCK_RAG: bool = Field(default=False, description="Tự động dùng Mock Data cho RAG tools khi backend offline")

    # logging/audit.py
    AUDIT_OUTPUT_DIR: str = Field(default="./output", description="Thư mục ghi file JSON audit mỗi lần evaluate")

    # agent/
    EVALUATE_TIMEOUT_SECONDS: int = Field(default=25, ge=1, description="Timeout tổng cho 1 lần /evaluate")
    MAX_REACT_STEP: int = Field(default=6, ge=1, description="Số bước Thought/Action tối đa mỗi vòng ReAct")
    MAX_REFLECT_STEP: int = Field(default=3, ge=1, description="Số vòng Review->Reflect->retry tối đa (Tmax)")
    MAX_RAG_CALLS: int = Field(default=5, ge=0, description="Giới hạn cứng số lần gọi RAG tool / request")
    CONFIDENCE_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0, description="Dưới ngưỡng này bắt buộc skip=true")

    @field_validator("BACKEND_BASE_URL")
    @classmethod
    def base_url_no_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")


settings = Settings()
