import logging
import os
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pythonjsonlogger import jsonlogger
from starlette.responses import Response

from . import rag

# ---- structured JSON logging (easy for Promtail/Loki to parse) ----
handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger("assistant")

# ---- Prometheus metrics ----
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["path"])
UPLOADS = Counter("pdf_uploads_total", "PDFs uploaded", ["outcome"])
QUESTIONS = Counter("questions_total", "Questions asked", ["outcome"])
LLM_LATENCY = Histogram("llm_answer_duration_seconds", "Retrieval + LLM time")

app = FastAPI(title="Enterprise AI Knowledge Assistant")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
store = rag.VectorStore()
UPLOAD_DIR = rag.DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        path = request.url.path
        elapsed = time.perf_counter() - start
        if path != "/metrics":
            REQUESTS.labels(request.method, path, str(status)).inc()
            LATENCY.labels(path).observe(elapsed)
            log.info("request", extra={"method": request.method, "path": path, "status": status, "ms": round(elapsed * 1000)})


class AskBody(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/documents")
def documents():
    return store.documents()


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".pdf"):
        UPLOADS.labels("rejected").inc()
        raise HTTPException(400, "Only PDF files are supported.")
    dest = UPLOAD_DIR / Path(file.filename).name
    dest.write_bytes(await file.read())
    try:
        info = store.add_pdf(file.filename, dest)
    except Exception as e:
        UPLOADS.labels("error").inc()
        log.exception("upload failed")
        raise HTTPException(422, str(e))
    UPLOADS.labels("ok").inc()
    log.info(
        "pdf indexed",
        extra={
            "doc_id": info["doc_id"],
            "pdf_filename": info["filename"],
            "pages": info["pages"],
            "chunks": info["chunks"],
        },
    )
    return info


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str):
    if not store.delete(doc_id):
        raise HTTPException(404, "Document not found.")
    return {"deleted": doc_id}


@app.post("/ask")
def ask(body: AskBody):
    q = body.question.strip()
    if not q:
        raise HTTPException(400, "Question is empty.")
    with LLM_LATENCY.time():
        hits = store.search(q)
        if not hits:
            QUESTIONS.labels("no_documents").inc()
            raise HTTPException(409, "Upload a PDF before asking questions.")
        try:
            text = rag.answer(q, hits)
        except Exception as e:
            QUESTIONS.labels("error").inc()
            log.exception("answer failed")
            raise HTTPException(503, f"Could not generate an answer: {e}")
    QUESTIONS.labels("ok").inc()
    sources = [
        {"filename": h["filename"], "page": h["page"], "score": round(h["score"], 3), "snippet": h["text"][:240]}
        for h in hits
    ]
    return {"answer": text, "sources": sources}


app = CORSMiddleware(
    app=app,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
