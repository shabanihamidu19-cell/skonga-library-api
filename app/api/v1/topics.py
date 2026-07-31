"""
SKONGA Library API — Topics Endpoints
========================================
GET /internal/v1/topics/{topic_id}
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import verify_service_token
from app.db.models import Topic
from app.db.session import get_db
from app.core.cache import cache_get, cache_set
from app.config import settings

router = APIRouter(prefix="/topics", tags=["Topics"])


class TopicDetail(BaseModel):
    id: str
    subject_id: str
    form_id: int
    order_index: int
    title_en: str
    title_sw: str
    competency_mkuu: str | None
    tags: list[str] | None
    related_topics: list[str] | None
    difficulty: str | None
    status: str
    content_version: int
    last_updated: str
    content_md: str | None


@router.get("/{topic_id}", response_model=TopicDetail)
def get_topic(
    topic_id: str,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_service_token),
):
    """
    Return the full detail for a single topic, including content_md
    (the curriculum notes in Markdown format) if available.
    """
    cache_key = f"topic:{topic_id}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t:
        raise HTTPException(status_code=404, detail=f"Topic '{topic_id}' not found")

    result = {
        "id": t.id,
        "subject_id": t.subject_id,
        "form_id": t.form_id,
        "order_index": t.order_index,
        "title_en": t.title_en,
        "title_sw": t.title_sw,
        "competency_mkuu": t.competency_mkuu,
        "tags": t.tags or [],
        "related_topics": t.related_topics or [],
        "difficulty": t.difficulty,
        "status": t.status,
        "content_version": t.content_version,
        "last_updated": str(t.last_updated),
        "content_md": t.content_md,
    }
    # Topics are cached slightly longer than subjects since they change less
    cache_set(cache_key, result, settings.CACHE_TTL_SUBJECTS * 2)
    return result
