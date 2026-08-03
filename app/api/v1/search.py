"""
SKONGA Library API — Search Endpoint (hardened)
================================================
Wraps the search function with defensive error handling and logging.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import log_request, log_error
from app.core.security import verify_service_token
from app.config import settings
from app.db.session import get_db
from app.retrieval.keyword_search import search_topics

router = APIRouter(prefix="/search", tags=["Search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    subject_id: str | None = None
    form_id: int | None = Field(None, ge=1, le=6)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    id: str
    subject_id: str
    form_id: int
    title_en: str
    title_sw: str
    difficulty: str | None
    relevance: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    retrieval_mode: str
    took_ms: float
    total: int


@router.post("", response_model=SearchResponse)
def search(
    body: SearchRequest,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_service_token),
):
    start = time.perf_counter()
    try:
        results, mode = search_topics(
            db=db,
            query=body.query,
            subject_id=body.subject_id,
            form_id=body.form_id,
            top_k=body.top_k,
        )

        took_ms = (time.perf_counter() - start) * 1000
        log_request(endpoint="/search", status_code=200, took_ms=took_ms,
                    extra={"retrieval_mode": mode, "results": len(results)})

        return {
            "results": results,
            "retrieval_mode": mode,
            "took_ms": round(took_ms, 2),
            "total": len(results),
        }
    except HTTPException:
        raise
    except Exception as exc:
        took_ms = (time.perf_counter() - start) * 1000
        log_error(endpoint="/search", error=str(exc), took_ms=took_ms)
        raise HTTPException(status_code=500, detail="Internal server error")
