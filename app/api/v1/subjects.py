"""
SKONGA Library API — Subjects Endpoints (hardened)
===================================================
Small defensive changes: catch unexpected exceptions, log them and return
HTTP 500 rather than crashing the whole worker.
"""
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.logging import log_error
from app.core.security import verify_service_token
from app.config import settings
from app.db.models import Subject, Topic
from app.db.session import get_db

router = APIRouter(prefix="/subjects", tags=["Subjects"])


class SubjectSummary(BaseModel):
    id: str
    name_en: str
    name_sw: str
    icon: str | None
    forms: list[int]
    topic_count: int


class SubjectDetail(SubjectSummary):
    schema_version: int
    last_updated: str


class TopicSummary(BaseModel):
    id: str
    subject_id: str
    form_id: int
    order_index: int
    title_en: str
    title_sw: str
    difficulty: str | None
    status: str


@router.get("", response_model=list[SubjectSummary])
def list_subjects(
    db: Session = Depends(get_db),
    _token: str = Depends(verify_service_token),
):
    cache_key = "subjects:all"
    try:
        cached = cache_get(cache_key)
        if cached:
            return cached

        subjects = db.query(Subject).order_by(Subject.name_en).all()
        result = []
        for s in subjects:
            forms = sorted({sf.form_id for sf in s.subject_forms})
            topic_count = db.query(Topic).filter(Topic.subject_id == s.id).count()
            result.append({
                "id": s.id,
                "name_en": s.name_en,
                "name_sw": s.name_sw,
                "icon": s.icon,
                "forms": forms,
                "topic_count": topic_count,
            })

        cache_set(cache_key, result, settings.CACHE_TTL_SUBJECTS)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log_error(endpoint="/subjects", error=str(exc))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{subject_id}", response_model=SubjectDetail)
def get_subject(
    subject_id: str,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_service_token),
):
    cache_key = f"subject:{subject_id}"
    try:
        cached = cache_get(cache_key)
        if cached:
            return cached

        s = db.query(Subject).filter(Subject.id == subject_id).first()
        if not s:
            raise HTTPException(status_code=404, detail=f"Subject '{subject_id}' not found")

        forms = sorted({sf.form_id for sf in s.subject_forms})
        topic_count = db.query(Topic).filter(Topic.subject_id == s.id).count()

        result = {
            "id": s.id,
            "name_en": s.name_en,
            "name_sw": s.name_sw,
            "icon": s.icon,
            "forms": forms,
            "topic_count": topic_count,
            "schema_version": s.schema_version,
            "last_updated": str(s.last_updated),
        }
        cache_set(cache_key, result, settings.CACHE_TTL_SUBJECTS)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log_error(endpoint="/subjects/{subject_id}", error=str(exc))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{subject_id}/forms/{form_id}/topics", response_model=list[TopicSummary])
def get_topics_for_form(
    subject_id: str,
    form_id: int,
    db: Session = Depends(get_db),
    _token: str = Depends(verify_service_token),
):
    if form_id < 1 or form_id > 6:
        raise HTTPException(status_code=422, detail="form_id must be between 1 and 6")

    cache_key = f"topics:{subject_id}:f{form_id}"
    try:
        cached = cache_get(cache_key)
        if cached:
            return cached

        topics = (
            db.query(Topic)
            .filter(Topic.subject_id == subject_id, Topic.form_id == form_id)
            .order_by(Topic.order_index)
            .all()
        )

        result = [
            {
                "id": t.id,
                "subject_id": t.subject_id,
                "form_id": t.form_id,
                "order_index": t.order_index,
                "title_en": t.title_en,
                "title_sw": t.title_sw,
                "difficulty": t.difficulty,
                "status": t.status,
            }
            for t in topics
        ]
        cache_set(cache_key, result, settings.CACHE_TTL_SUBJECTS)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log_error(endpoint="/subjects/{subject_id}/forms/{form_id}/topics", error=str(exc))
        raise HTTPException(status_code=500, detail="Internal server error")
