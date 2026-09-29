import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from google import genai
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from models.document import Embedding
except ImportError:
    Embedding = None

from app.config.settings import settings
import logging
import asyncio

def get_ollama_base_url() -> str:
    return getattr(settings, "OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

def get_embedding_model() -> str:
    return getattr(settings, "OLLAMA_EMBEDDING_MODEL", getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text"))

CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
EMBEDDING_DIM = getattr(settings, "EMBEDDING_DIM", 768)
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY")) if os.getenv("GEMINI_API_KEY") else None
logger = logging.getLogger(__name__)


async def get_embedding(text: str) -> list[float]:
    """
    Generate embedding vector for input text matching settings.EMBEDDING_DIM.
    Prioritizes Voyage AI if VOYAGE_API_KEY is set, else Ollama (nomic-embed-text) or fallback vector.
    """
    target_dim = getattr(settings, "EMBEDDING_DIM", 768)
    if getattr(settings, "VOYAGE_API_KEY", ""):
        try:
            req = Request(
                "https://api.voyageai.com/v1/embeddings",
                data=json.dumps({
                    "model": getattr(settings, "EMBEDDING_MODEL", "voyage-3"),
                    "input": [text],
                }).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.VOYAGE_API_KEY}",
                },
                method="POST",
            )
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, lambda: urlopen(req, timeout=10).read().decode("utf-8"))
            data = json.loads(res)
            vec = data["data"][0]["embedding"]
            if len(vec) == target_dim:
                return vec
            logger.warning("Voyage AI embedding dimension mismatch: expected %d, got %d", target_dim, len(vec))
        except Exception as e:
            logger.warning("Voyage AI embedding request failed: %s", e)

    # Ưu tiên Ollama với nomic-embed-text
    try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            None,
            lambda: post_ollama("/api/embed", {"model": get_embedding_model(), "input": [text]}),
        )
        vecs = res.get("embeddings", [])
        if vecs and len(vecs[0]) == target_dim:
            return vecs[0]
        elif vecs:
            logger.warning("Ollama embedding dimension mismatch: expected %d, got %d", target_dim, len(vecs[0]))
            return vecs[0]
    except Exception as ollama_err:
        logger.debug("Ollama embedding call failed: %s", ollama_err)

    # Default fallback: return zero vector of correct dimension
    return [0.0] * target_dim



def chunk_text(text: str, chunk_size: int = 3500, overlap: int = 500) -> list[str]:
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap

    return chunks


def post_ollama(path: str, payload: dict) -> dict:
    base_url = get_ollama_base_url()
    url = f"{base_url}{path}"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8")
        raise RuntimeError(f"Ollama request failed ({e.code}): {detail}") from e
    except URLError as e:
        raise RuntimeError(f"Cannot connect to Ollama at {base_url}: {e}") from e


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model_name = get_embedding_model()
    result = post_ollama("/api/embed", {
        "model": model_name,
        "input": texts,
    })
    vectors = result.get("embeddings")
    if vectors is None:
        raise RuntimeError(f"Ollama embedding response missing 'embeddings': {result}")

    target_dim = getattr(settings, "EMBEDDING_DIM", 768)
    for vector in vectors:
        if len(vector) != target_dim:
            logger.warning("Embedding dimension: expected %d, got %d", target_dim, len(vector))

    return vectors


def embed_texts_in_batches(texts: list[str]) -> list[list[float]]:
    vectors = []

    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start:start + EMBEDDING_BATCH_SIZE]
        vectors.extend(embed_texts(batch))

    return vectors


async def index_document(db: AsyncSession, document_id, markdown_text: str):
    await db.execute(delete(Embedding).where(Embedding.doc_id == document_id))

    chunks = chunk_text(markdown_text)
    if not chunks:
        return

    embed_inputs = [
        f"Represent this document chunk for retrieval:\n{chunk}"
        for chunk in chunks
    ]
    vectors = embed_texts_in_batches(embed_inputs)

    for chunk, vector in zip(chunks, vectors):
        db.add(Embedding(
            doc_id=document_id,
            emb_chunk=chunk,
            emb_vector=vector,
        ))

    await db.commit()


def embed_query(question: str) -> list[float]:
    return embed_texts([
        f"Represent this user question for retrieving relevant document chunks:\n{question}"
    ])[0]


async def vector_search(db: AsyncSession, question: str, limit: int = 8):
    query_vector = embed_query(question)

    result = await db.execute(
        select(Embedding)
        .order_by(Embedding.emb_vector.cosine_distance(query_vector))
        .limit(limit)
    )

    return result.scalars().all()

"""
async def fts_search(db: AsyncSession, question: str, limit: int = 8):
    query = func.plainto_tsquery("simple", question)

    result = await db.execute(
        select(Embedding)
        .where(Embedding.emb_fts.op("@@")(query))
        .order_by(func.ts_rank_cd(Embedding.emb_fts, query).desc())
        .limit(limit)
    )

    return result.scalars().all()
"""

async def hybrid_search(db: AsyncSession, question: str, limit: int = 8):
    vector_results = await vector_search(db, question, limit)
    fts_results = await fts_search(db, question, limit)

    merged = []
    seen = set()

    for item in vector_results + fts_results:
        if item.emb_id not in seen:
            merged.append(item)
            seen.add(item.emb_id)

    return merged[:limit]


def generate_answer(question: str, chunks: list[Embedding]) -> str:
    context = "\n\n---\n\n".join(chunk.emb_chunk for chunk in chunks)

    prompt = f"""
You are a chatbot for reading novel/document content.

Only answer using the CONTEXT.
If the CONTEXT is not enough, say that there is not enough information.

CONTEXT:
{context}

QUESTION:
{question}
"""

    response = gemini_client.models.generate_content(
        model=CHAT_MODEL,
        contents=prompt,
    )

    return response.text