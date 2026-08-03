# RAG Latency Fixes (Phase 1.1)

Changes applied on top of the upstream `skonga-library-api` repo.

## What changed

### 1. `app/retrieval/keyword_search.py`
- `plainto_tsquery` evaluated **once** via CTE (was twice per query).
- `content_md` only SELECTed when `include_content=True` (smaller payloads).
- **ILIKE fuzzy fallback only runs when `subject_id` or `form_id` is set** —
  unbounded `%query%` scans were the main latency spike.
- New retrieval mode: `fulltext_empty` when nothing matched and fallback was skipped.
- Pattern length capped at 80 chars for fuzzy path.

### 2. `app/api/v1/rag.py`
- Cache key **normalizes** query (lowercase + whitespace) and includes `include_content`.
- Stage timings: `cache_ms`, `search_ms`, `build_ms`, `cache_hit`.
  - Included in JSON response when `ENVIRONMENT != production`.
  - Always written to structured logs.

### 3. `app/api/v1/search.py`
- Passes `include_content` (default **False** for search — metadata only).
- Strips `content_md` from list response.

### 4. `app/core/logging.py`
- `log_rag_request` accepts optional `extra` dict (timing fields).

### 5. `app/db/migrations/latency_indexes.sql` (new, optional)
- `pg_trgm` GIN indexes for title fuzzy match.
- Composite `(status, subject_id, form_id)` index.

## How to verify

```bash
# Development: response includes timing breakdown
curl -s -X POST "$API/internal/v1/rag/context" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"photosynthesis","subject_hint":"biology","form_hint":1,"top_k":5}' \
  | jq '{took_ms, retrieval_mode, cache_hit, cache_ms, search_ms, build_ms, topics_found}'
```

Watch logs for:
```json
{"endpoint":"/rag/context","took_ms":...,"search_ms":...,"cache_hit":false,"retrieval_mode":"fulltext"}
```

## Recommended production setup

1. Set `REDIS_URL` so repeated queries are sub-15 ms.
2. Run `latency_indexes.sql` on Supabase if you rely on fuzzy fallback.
3. Always pass `subject_hint` / `form_hint` from the AI backend when known.
4. Co-locate Render region with Supabase region.

## Expected latency

| Scenario | Before | After |
|----------|--------|-------|
| Cache hit | n/a or slow | ~1–15 ms |
| Full-text hit | 20–80 ms | 15–60 ms (less payload) |
| Full-text miss, no filters | 100–600+ ms (ILIKE scan) | ~20–80 ms (skip fallback) |
| Full-text miss + subject filter | 50–300 ms | 30–120 ms (bounded) |
