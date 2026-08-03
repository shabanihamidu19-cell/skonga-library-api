"""
SKONGA Library API — Keyword Search (Phase 1)
===============================================
Uses Postgres tsvector/tsquery for full-text search over topic titles.
This is the Phase 1 retrieval engine — Phase 2 will add vector
(semantic) search on top of this, keeping the keyword path as a
fast fallback.

Latency notes (Phase 1.1):
  - plainto_tsquery is computed once via CTE (was evaluated twice).
  - content_md is only SELECTed when include_content=True.
  - ILIKE fuzzy fallback runs ONLY when subject_id or form_id is set
    (leading-wildcard ILIKE cannot use indexes → sequential scan).
  - Without filters, empty full-text result returns immediately.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def _content_select(include_content: bool) -> str:
    return "content_md," if include_content else "NULL::text AS content_md,"


def keyword_search(
    db: Session,
    query: str,
    subject_id: str | None = None,
    form_id: int | None = None,
    top_k: int = 5,
    status_filter: str = "published",
    include_content: bool = True,
) -> list[dict]:
    """
    Search topics by keyword using Postgres full-text search.

    Returns a list of dicts (not ORM objects) for easy JSON serialisation.
    Each dict contains: id, subject_id, form_id, title_en, title_sw,
    difficulty, status, content_md (or None), relevance (float).
    """
    filters = ["status = :status"]
    params: dict = {"query": query, "status": status_filter, "top_k": top_k}

    if subject_id:
        filters.append("subject_id = :subject_id")
        params["subject_id"] = subject_id

    if form_id:
        filters.append("form_id = :form_id")
        params["form_id"] = form_id

    where_clause = " AND ".join(filters)
    content_col = _content_select(include_content)

    # CTE evaluates plainto_tsquery once (avoids double computation in
    # SELECT rank + WHERE match).
    sql = text(f"""
        WITH q AS (
            SELECT plainto_tsquery('simple', :query) AS tsq
        )
        SELECT
            t.id,
            t.subject_id,
            t.form_id,
            t.order_index,
            t.title_en,
            t.title_sw,
            t.difficulty,
            t.status,
            {content_col}
            ts_rank(t.search_vector, q.tsq) AS relevance
        FROM topics t, q
        WHERE {where_clause}
          AND t.search_vector @@ q.tsq
        ORDER BY relevance DESC
        LIMIT :top_k
    """)

    rows = db.execute(sql, params).mappings().all()
    return [dict(row) for row in rows]


def fuzzy_fallback(
    db: Session,
    query: str,
    subject_id: str | None = None,
    form_id: int | None = None,
    top_k: int = 5,
    include_content: bool = True,
) -> list[dict]:
    """
    ILIKE-based fallback for when the full-text query returns zero results
    (e.g. the user typed a partial word or a word not in the tsvector index).

    WARNING: leading-wildcard ILIKE cannot use B-tree/GIN indexes and can
    cause sequential scans. Callers must only invoke this when subject_id
    and/or form_id narrow the candidate set.
    """
    filters = ["status = 'published'"]
    # Cap pattern length to avoid pathological scans
    safe_query = (query or "").strip()[:80]
    params: dict = {"pattern": f"%{safe_query}%", "top_k": top_k}

    if subject_id:
        filters.append("subject_id = :subject_id")
        params["subject_id"] = subject_id
    if form_id:
        filters.append("form_id = :form_id")
        params["form_id"] = form_id

    where_clause = " AND ".join(filters)
    content_col = _content_select(include_content)

    sql = text(f"""
        SELECT
            id, subject_id, form_id, order_index,
            title_en, title_sw, difficulty, status,
            {content_col}
            0.5 AS relevance
        FROM topics
        WHERE {where_clause}
          AND (title_en ILIKE :pattern OR title_sw ILIKE :pattern)
        ORDER BY order_index
        LIMIT :top_k
    """)

    rows = db.execute(sql, params).mappings().all()
    return [dict(row) for row in rows]


def search_topics(
    db: Session,
    query: str,
    subject_id: str | None = None,
    form_id: int | None = None,
    top_k: int = 5,
    include_content: bool = True,
) -> tuple[list[dict], str]:
    """
    Entry-point for the retrieval layer: tries full-text first,
    falls back to ILIKE only when subject/form filters are present
    (so the scan is bounded).

    Returns (results, retrieval_mode) where retrieval_mode is
    'fulltext', 'fuzzy_fallback', or 'fulltext_empty'.
    """
    results = keyword_search(
        db, query, subject_id, form_id, top_k, include_content=include_content
    )
    if results:
        return results, "fulltext"

    # Avoid unbounded sequential scan when no filters are provided.
    if subject_id or form_id:
        results = fuzzy_fallback(
            db, query, subject_id, form_id, top_k, include_content=include_content
        )
        if results:
            return results, "fuzzy_fallback"

    return [], "fulltext_empty"
