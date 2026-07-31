"""
SKONGA Library API — Structured Logging
=========================================
Outputs JSON lines so logs can be parsed by Render's log drain,
Logtail, or any log aggregator.

Privacy note: query text is HASHED before logging (SHA-256 first 16 chars)
so sensitive student queries never appear in plaintext in the log store.
"""
import hashlib
import json
import logging
import time
from typing import Any

from app.config import settings

logging.basicConfig(level=settings.LOG_LEVEL.upper())
_log = logging.getLogger("skonga_library")


def _hash_query(query: str) -> str:
    """Short hash of a user query for correlation without exposing content."""
    return hashlib.sha256(query.encode()).hexdigest()[:16]


def log_request(
    endpoint: str,
    status_code: int,
    took_ms: float,
    extra: dict[str, Any] | None = None,
) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": "INFO" if status_code < 400 else "WARNING",
        "endpoint": endpoint,
        "status": status_code,
        "took_ms": round(took_ms, 2),
        "env": settings.ENVIRONMENT,
    }
    if extra:
        record.update(extra)
    _log.info(json.dumps(record))


def log_rag_request(
    query: str,
    subject_hint: str | None,
    form_hint: int | None,
    status_code: int,
    took_ms: float,
    retrieval_mode: str,
    results_count: int,
) -> None:
    log_request(
        endpoint="/rag/context",
        status_code=status_code,
        took_ms=took_ms,
        extra={
            "query_hash": _hash_query(query),
            "subject_hint": subject_hint,
            "form_hint": form_hint,
            "retrieval_mode": retrieval_mode,
            "results_count": results_count,
        },
    )


def log_error(endpoint: str, error: str, took_ms: float = 0.0) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": "ERROR",
        "endpoint": endpoint,
        "error": error,
        "took_ms": round(took_ms, 2),
        "env": settings.ENVIRONMENT,
    }
    _log.error(json.dumps(record))
