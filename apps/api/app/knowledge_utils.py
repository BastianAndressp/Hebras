from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import httpx
from .config import settings


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunks.append(" ".join(words[start:end]).strip())
        if end >= len(words):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def chunk_score(query: str, chunk: str) -> int:
    query_terms = {term for term in query.lower().split() if len(term) > 2}
    if not query_terms:
        return 0
    chunk_terms = set(chunk.lower().split())
    return sum(1 for term in query_terms if term in chunk_terms)


async def generate_embedding(text: str) -> list[float]:
    """Genera un vector embedding de 1536 dimensiones."""
    if settings.openrouter_api_key and settings.openrouter_api_key != "mock_key":
        try:
            headers = {
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": "openai/text-embedding-3-small",
                "input": text[:2000],
            }
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{settings.openrouter_base_url}/embeddings",
                    headers=headers,
                    json=body,
                )
                if response.status_code == 200:
                    data = response.json()
                    embedding = data.get("data", [{}])[0].get("embedding")
                    if embedding and len(embedding) == 1536:
                        return embedding
        except Exception:
            pass

    # Fallback determinista de 1536 dimensiones normalizado para entonos dev/demo/sin API key
    vec = []
    text_bytes = text.encode("utf-8")
    for i in range(1536):
        h = hashlib.sha256(text_bytes + i.to_bytes(4, "big")).digest()
        val = (int.from_bytes(h[:4], "big") / (2**32 - 1)) * 2.0 - 1.0
        vec.append(val)
    norm = (sum(x * x for x in vec) ** 0.5) or 1.0
    return [x / norm for x in vec]


def extract_text_from_upload(filename: str, content_type: str | None, data: bytes) -> str:
    suffix = Path(filename.lower()).suffix
    if suffix in {".txt", ".md", ".csv"} or content_type in {"text/plain", "text/markdown", "text/csv"}:
        return data.decode("utf-8", errors="ignore").strip()

    if suffix == ".pdf" or content_type == "application/pdf":
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n\n".join(page for page in pages if page).strip()

    if suffix == ".docx" or content_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }:
        from docx import Document

        document = Document(BytesIO(data))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n\n".join(paragraphs).strip()

    return data.decode("utf-8", errors="ignore").strip()