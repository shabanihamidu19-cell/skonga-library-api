-- SKONGA Library API — Optional latency indexes (Phase 1.1)
-- Run on Supabase SQL editor AFTER initial_schema.sql if fuzzy search is needed.
-- Safe to re-run (IF NOT EXISTS / IF NOT EXISTS patterns).

-- 1) Trigram extension for indexed fuzzy title matching (replaces slow ILIKE %x%)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_topics_title_en_trgm
    ON topics USING GIN (title_en gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_topics_title_sw_trgm
    ON topics USING GIN (title_sw gin_trgm_ops);

-- 2) Composite filter used by RAG when subject + form hints are present
CREATE INDEX IF NOT EXISTS idx_topics_status_subject_form
    ON topics (status, subject_id, form_id);

-- Optional later: expand search_vector to include truncated content_md
-- (requires dropping GENERATED column and recreating — do in a dedicated migration)
--
-- ALTER TABLE topics DROP COLUMN search_vector;
-- ALTER TABLE topics ADD COLUMN search_vector TSVECTOR
--   GENERATED ALWAYS AS (
--     to_tsvector('simple',
--       coalesce(title_en,'') || ' ' ||
--       coalesce(title_sw,'') || ' ' ||
--       left(coalesce(content_md,''), 2000)
--     )
--   ) STORED;
-- CREATE INDEX idx_topics_search ON topics USING GIN (search_vector);
