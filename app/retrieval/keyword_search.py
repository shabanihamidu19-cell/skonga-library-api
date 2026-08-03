"""
SKONGA Library API — Keyword Search (Phase 1)
===============================================
Uses Postgres tsvector/tsquery for full-text search over topic titles.
This is the Phase 1 retrieval engine — Phase 2 will add vector
(semantic) search on top of this, keeping the keyword path as a
fast fallback.

Design: a two-stage query:
  1. Filter by subject_id / form_id if hints are provided (fast index)
  2. Rank remaining topics by full-text relevance score
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Topic


def keyword_search(
    db: Session,
    query: str,
    subject_id: str | None = None,
    form_id: int | None = None,
    top_k: int = 5,
    status_filter: str = "published",
) -> list[dict]:
    """
    Search topics by keyword using Postgres full-text search.

    Returns a list of dicts (not ORM objects) for easy JSON serialisation.
    Each dict contains: id, subject_id, form_id, title_en, title_sw,
    difficulty, status, relevance (float).
    """
    if not query or not isinstance(query, str):
        raise ValueError("query must be a non-empty string")

    # sanitize and cap top_k
    try:
        top_k = max(1, min(int(top_k), 50))
    except Exception:
        top_k = 5

    # Build the parameterised query.
    filters = ["status = :status"]
    params: dict = {"query": query, "status": status_filter, "top_k": top_k}

    if subject_id:
        filters.append("subject_id = :subject_id")
        params["subject_id"] = subject_id

    if form_id:
        filters.append("form_id = :form_id")
        params["form_id"] = form_id

    where_clause = " AND ".join(filters)

    # plainto_tsquery converts a natural language query to a tsquery safely
    # (no syntax errors from user input, unlike to_tsquery).
    sql = text(f"""
        SELECT
            id,
            subject_id,
            form_id,
            order_index,
            title_en,
            title_sw,
            difficulty,
            status,
            content_md,
            ts_rank(search_vector, plainto_tsquery('simple', :query)) AS relevance
        FROM topics
        WHERE {where_clause}
          AND search_vector @@ plainto_tsquery('simple', :query)
        ORDER BY relevance DESC
        LIMIT :top_k
    """)

    rows = db.execute(sql, params).mappings().all()
    results = []
    for row in rows:
        r = dict(row)
        # ensure relevance is a float for JSON serialisation
        try:
            r["relevance"] = float(r.get("relevance") or 0.0)
        except Exception:
            r["relevance"] = 0.0
        results.append(r)
    return results


def fuzzy_fallback(
    db: Session,
    query: str,
    subject_id: str | None = None,
    form_id: int | None = None,
    top_k: int = 5,
) -> list[dict]:
    """
    ILIKE-based fallback for when the full-text query returns zero results
    (e.g. the user typed a partial word or a word not in the tsvector index).
    Slower than tsvector but covers edge cases gracefully.
    """
    if not query or not isinstance(query, str):
        raise ValueError("query must be a non-empty string")

    try:
        top_k = max(1, min(int(top_k), 50))
    except Exception:
        top_k = 5

    filters = ["status = 'published'"]
    params: dict = {"pattern": f"%{query}%", "top_k": top_k}

    if subject_id:
        filters.append("subject_id = :subject_id")
        params["subject_id"] = subject_id
    if form_id:
        filters.append("form_id = :form_id")
        params["form_id"] = form_id

    where_clause = " AND ".join(filters)

    sql = text(f"""
        SELECT
            id, subject_id, form_id, order_index,
            title_en, title_sw, difficulty, status,
            content_md,
            0.5 AS relevance
        FROM topics
        WHERE {where_clause}
          AND (title_en ILIKE :pattern OR title_sw ILIKE :pattern)
        ORDER BY order_index
        LIMIT :top_k
    """)

    rows = db.execute(sql, params).mappings().all()
    results = []
    for row in rows:
        r = dict(row)
        r["relevance"] = 0.5
        results.append(r)
    return results


def search_topics(
    db: Session,
    query: str,
    subject_id: str | None = None,
    form_id: int | None = None,
    top_k: int = 5,
) -> tuple[list[dict], str]:
    """
    Entry-point for the retrieval layer: tries full-text first,
    falls back to ILIKE if no results.
    Returns (results, retrieval_mode) where retrieval_mode is
    'fulltext' or 'fuzzy_fallback' — logged for diagnostics.
    """
    results = keyword_search(db, query, subject_id, form_id, top_k)
    if results:
        return results, "fulltext"

    results = fuzzy_fallback(db, query, subject_id, form_id, top_k)
    return results, "fuzzy_fallback"
