-- SKONGA Library API — Initial Schema (Phase 1)
-- Run via: python3 -m alembic upgrade head
-- OR directly on Supabase SQL editor for first-time setup.

CREATE TABLE IF NOT EXISTS subjects (
    id             TEXT PRIMARY KEY,
    name_en        TEXT NOT NULL,
    name_sw        TEXT NOT NULL,
    icon           TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1,
    last_updated   DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS forms (
    id SMALLINT PRIMARY KEY CHECK (id BETWEEN 1 AND 6)
);

INSERT INTO forms (id) VALUES (1),(2),(3),(4),(5),(6)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS subject_forms (
    subject_id TEXT     REFERENCES subjects(id) ON DELETE CASCADE,
    form_id    SMALLINT REFERENCES forms(id),
    PRIMARY KEY (subject_id, form_id)
);

CREATE TABLE IF NOT EXISTS topics (
    id               TEXT PRIMARY KEY,
    subject_id       TEXT     NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    form_id          SMALLINT NOT NULL REFERENCES forms(id),
    order_index      INTEGER  NOT NULL,
    title_en         TEXT     NOT NULL,
    title_sw         TEXT     NOT NULL,
    competency_mkuu  TEXT,
    tags             TEXT[],
    related_topics   TEXT[],
    difficulty       TEXT CHECK (difficulty IN ('foundational','intermediate','advanced')),
    status           TEXT NOT NULL DEFAULT 'skeleton'
                     CHECK (status IN ('skeleton','draft','reviewed','published')),
    content_version  INTEGER NOT NULL DEFAULT 1,
    last_updated     DATE    NOT NULL,
    content_md       TEXT,

    -- Full-text search vector (auto-maintained by Postgres)
    -- covers both English and Swahili titles
    search_vector    TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(title_en,'') || ' ' || coalesce(title_sw,''))
    ) STORED
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_topics_subject_form ON topics (subject_id, form_id);
CREATE INDEX IF NOT EXISTS idx_topics_search ON topics USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_topics_status ON topics (status);
