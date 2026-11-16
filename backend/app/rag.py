"""RAG core: PDF -> chunks -> embeddings -> retrieval -> grounded answer."""
import json
import os
import threading
import uuid
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
TOP_K = 5

_embedder = None


def embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def chunk_text(text: str) -> list[str]:
    text = " ".join(text.split())
    step = CHUNK_SIZE - CHUNK_OVERLAP
    pieces = (text[i : i + CHUNK_SIZE] for i in range(0, len(text), step))
    return [p for p in pieces if p.strip()]


class VectorStore:
    """Tiny persistent vector store (cosine similarity via numpy).
    Swap for FAISS or ChromaDB if the corpus grows."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.meta_path = DATA_DIR / "chunks.json"
        self.vec_path = DATA_DIR / "vectors.npy"
        self.lock = threading.Lock()
        self.chunks: list[dict] = []
        self.vectors = np.zeros((0, 384), dtype="float32")
        if self.meta_path.exists() and self.vec_path.exists():
            self.chunks = json.loads(self.meta_path.read_text())
            self.vectors = np.load(self.vec_path)

    def _save(self):
        self.meta_path.write_text(json.dumps(self.chunks))
        np.save(self.vec_path, self.vectors)

    def add_pdf(self, filename: str, path: Path) -> dict:
        reader = PdfReader(str(path))
        doc_id = uuid.uuid4().hex[:8]
        new_chunks = []
        for page_no, page in enumerate(reader.pages, start=1):
            for piece in chunk_text(page.extract_text() or ""):
                new_chunks.append(
                    {"doc_id": doc_id, "filename": filename, "page": page_no, "text": piece}
                )
        if not new_chunks:
            raise ValueError("No extractable text found (scanned PDF?)")
        vecs = embedder().encode(
            [c["text"] for c in new_chunks], normalize_embeddings=True
        ).astype("float32")
        with self.lock:
            self.chunks.extend(new_chunks)
            self.vectors = np.vstack([self.vectors, vecs]) if len(self.vectors) else vecs
            self._save()
        return {"doc_id": doc_id, "filename": filename, "pages": len(reader.pages), "chunks": len(new_chunks)}

    def documents(self) -> list[dict]:
        docs: dict[str, dict] = {}
        for c in self.chunks:
            d = docs.setdefault(c["doc_id"], {"doc_id": c["doc_id"], "filename": c["filename"], "chunks": 0})
            d["chunks"] += 1
        return list(docs.values())

    def delete(self, doc_id: str) -> bool:
        with self.lock:
            keep = [i for i, c in enumerate(self.chunks) if c["doc_id"] != doc_id]
            if len(keep) == len(self.chunks):
                return False
            self.chunks = [self.chunks[i] for i in keep]
            self.vectors = self.vectors[keep] if keep else np.zeros((0, 384), dtype="float32")
            self._save()
        return True

    def search(self, question: str, k: int = TOP_K) -> list[dict]:
        if not len(self.chunks):
            return []
        q = embedder().encode([question], normalize_embeddings=True).astype("float32")[0]
        scores = self.vectors @ q
        top = np.argsort(-scores)[:k]
        return [{**self.chunks[i], "score": float(scores[i])} for i in top]


SYSTEM_PROMPT = (
    "You answer questions using ONLY the provided document excerpts. "
    "Cite sources inline as [filename p.N]. If the excerpts do not contain the answer, "
    "say you could not find it in the uploaded documents. Be concise."
)


def answer(question: str, hits: list[dict]) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    context = "\n\n".join(f"[{h['filename']} p.{h['page']}]\n{h['text']}" for h in hits)
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    completion = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        max_tokens=800,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Excerpts:\n{context}\n\nQuestion: {question}"},
        ],
    )
    response = completion.choices[0].message.content
    if response is None:
        raise RuntimeError("OpenRouter returned an empty response")
    return response
