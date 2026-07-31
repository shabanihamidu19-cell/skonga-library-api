"""
SKONGA Library API — RAG Context Endpoint
============================================
POST /internal/v1/rag/context

This is the single most important endpoint in the entire service.
The SKONGA AI backend calls this BEFORE sending any message to the LLM.
The response provides:
  - context_text: a formatted block ready to inject into the LLM system prompt
  - citations: structured topic references for the UI to display ("Source: ...")

Flow:
  1. SKONGA AI Backend receives student question
  2. Calls POST /rag/context with the question + optional hints
  3. This endpoint retrieves the most relevant curriculum topics
  4. Builds and returns context_text + citations
  5. AI Backend injects context_text into LLM prompt
  6. LLM generates a curriculum-aligned answer
"""
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.cache import cache_get, cache_set
from app.core.logging import log_rag_request
from app.core.security import verify_service_token
from app.db.session import get_db
from app.retrieval.context_builder import build_context
from app.retrieval.keyword_search import search_topics

router = APIRouter(prefix="/rag", tags=["RAG"])


class RAGRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000,
                       description="The student's question or message")
    subject_hint: str | None = Field(
        None,
        description="Subject ID inferred from conversation context (e.g. 'biology'). "
                    "Omit if unknown — the retrieval engine will search across all subjects."
    )
    form_hint: int | None = Field(
        None, ge=1, le=6,
        description="Student's form/grade level (1-6) if known from their profile."
    )
    top_k: int = Field(
        default=5, ge=1, le=10,
        description="Maximum number of curriculum topics to retrieve."
    )
    include_content: bool = Field(
        default=True,
        description="Whether to include content_md (curriculum notes) in the context. "
                    "Set False if you only need topic metadata."
    )


class Citation(BaseModel):
    topic_id: str
    title_sw: str
    title_en: str
    subject_id: str | None
    form_id: int | None
    relevance: float


class RAGResponse(BaseModel):
    context_text: str
    citations: list[Citation]
    retrieval_mode: str
    topics_found: int
    took_ms: float
    curriculum_aligned: bool


@router.post("/context", response_model=RAGResponse)
def get_rag_context(
    body: RAGRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_service_token),
):
    """
    Retrieve curriculum-aligned context for AI generation.

    Called by SKONGA AI Backend before every LLM call.
    Returns a ready-to-use context block and structured citations.
    """
    start = time.perf_counter()

    # Cache key: hash of the query + hints
    import hashlib
    raw_key = f"{body.query}|{body.subject_hint}|{body.form_hint}|{body.top_k}"
    cache_key = "rag:" + hashlib.sha256(raw_key.encode()).hexdigest()[:24]

    cached = cache_get(cache_key)
    if cached:
        took_ms = (time.perf_counter() - start) * 1000
        cached["took_ms"] = round(took_ms, 2)
        return cached

    # ── Retrieval ──────────────────────────────────────────────────────────
    topics, retrieval_mode = search_topics(
        db=db,
        query=body.query,
        subject_id=body.subject_hint,
        form_id=body.form_hint,
        top_k=body.top_k,
    )

    # ── Context assembly ───────────────────────────────────────────────────
    context_text, citations = build_context(topics, retrieval_mode, include_content=body.include_content)

    took_ms = (time.perf_counter() - start) * 1000
    log_rag_request(
        query=body.query,
        subject_hint=body.subject_hint,
        form_hint=body.form_hint,
        status_code=200,
        took_ms=took_ms,
        retrieval_mode=retrieval_mode,
        results_count=len(topics),
    )

    result = {
        "context_text": context_text,
        "citations": citations,
        "retrieval_mode": retrieval_mode,
        "topics_found": len(topics),
        "took_ms": round(took_ms, 2),
        "curriculum_aligned": len(topics) > 0,
    }

    # Cache only if we got results (empty results may improve with more data)
    if topics:
        cache_set(cache_key, result, settings.CACHE_TTL_RAG)

    return result
