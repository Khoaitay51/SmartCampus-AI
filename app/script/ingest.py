"""
app/script/ingest.py
--------------------
Script quét các file Markdown trong campus_knowledge/
và nạp vào bảng agent_memory.campus_documents (pgvector + FTS).

Cách chạy:
    python -m app.script.ingest
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import uuid
from pathlib import Path

# Đảm bảo import được module app khi chạy từ root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.models import CampusKnowledgeDocument
from app.database.session import async_session, init_db
from app.gateway.embeddings import chunk_text, get_embedding

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest")

KNOWLEDGE_DIR = PROJECT_ROOT / "campus_knowledge"


def extract_title(content: str, default: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else default


def infer_doc_type(filename: str) -> str:
    clean_name = filename.replace(".md", "").lower()
    if "smoke" in clean_name or "fire" in clean_name:
        return "sop_smoke_fire"
    if "temperature" in clean_name or "hvac" in clean_name:
        return "sop_temperature_hvac"
    if "occupancy" in clean_name or "exam" in clean_name:
        return "sop_occupancy_exam"
    if "rfid" in clean_name or "security" in clean_name:
        return "sop_rfid_security"
    return "general_sop"


async def ingest_file(file_path: Path) -> int:
    raw_text = file_path.read_text(encoding="utf-8")
    title = extract_title(raw_text, default=file_path.stem)
    doc_type = infer_doc_type(file_path.name)

    chunks = chunk_text(raw_text, chunk_size=500, overlap=100)
    logger.info("Đang xử lý '%s' (%d chunks, doc_type=%s)...", file_path.name, len(chunks), doc_type)

    count = 0
    async with async_session() as session:
        for idx, chunk in enumerate(chunks):
            vec = await get_embedding(chunk)

            doc = CampusKnowledgeDocument(
                id=str(uuid.uuid4()),
                doc_type=doc_type,
                title=f"{title} (Phần {idx + 1})",
                content=chunk,
                embedding=vec,
                metadata_={
                    "source_file": file_path.name,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                },
            )
            session.add(doc)
            count += 1

        await session.commit()

    return count


async def main() -> None:
    if not KNOWLEDGE_DIR.exists():
        logger.error("Thư mục '%s' không tồn tại!", KNOWLEDGE_DIR)
        return

    await init_db()

    md_files = sorted(list(KNOWLEDGE_DIR.glob("*.md")))
    if not md_files:
        logger.warning("Không tìm thấy file .md nào trong %s", KNOWLEDGE_DIR)
        return

    logger.info("Bắt đầu nạp %d tài liệu vào Knowledge Store...", len(md_files))
    total_chunks = 0
    for md_file in md_files:
        chunks_inserted = await ingest_file(md_file)
        total_chunks += chunks_inserted

    logger.info("🎉 HOÀN TẤT: Đã nạp thành công %d chunks từ %d tài liệu vào pgvector!", total_chunks, len(md_files))


if __name__ == "__main__":
    asyncio.run(main())
