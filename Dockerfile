FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        fastapi[standard] \
        sqlalchemy \
        asyncpg \
        pgvector \
        python-dotenv \
        pydantic-settings \
        httpx \
        google-genai

CMD ["python", "run_agent_demo.py"]
