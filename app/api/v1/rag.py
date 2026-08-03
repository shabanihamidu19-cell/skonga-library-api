"""
SKONGA Library API — RAG Context Endpoint
============================================
Handles POST /internal/v1/rag/context — returns context_text and citations
for the AI backend. Defensive: catches unexpected errors, logs them and
returns a 500 without exposing internal details.
"""
import time
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.core.cache import cache_get, cache_set
from app.core.logging import log_rag_request, log_error
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
    start = time.perf_counter()

    try:
        raw_key = f"{body.query}|{body.subject_hint}|{body.form_hint}|{body.top_k}"
        cache_key = "rag:" + hashlib.sha256(raw_key.encode()).hexdigest()[:24]

        cached = cache_get(cache_key)
        if cached:
            took_ms = (time.perf_counter() - start) * 1000
            # return a shallow copy to avoid mutating cached data in Redis
            cached_copy = dict(cached)
            cached_copy["took_ms"] = round(took_ms, 2)
            return cached_copy

        topics, retrieval_mode = search_topics(
            db=db,
            query=body.query,
            subject_id=body.subject_hint,
            form_id=body.form_hint,
            top_k=body.top_k,
        )

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

        if topics:
            cache_set(cache_key, result, settings.CACHE_TTL_RAG)

        return result

    except HTTPException:
        # Re-raise FastAPI HTTP exceptions unchanged
        raise
    except Exception as exc:
        # Log internal errors and return a generic 500
        took_ms = (time.perf_counter() - start) * 1000
        log_error(endpoint="/rag/context", error=str(exc), took_ms=took_ms)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Internal server error")
