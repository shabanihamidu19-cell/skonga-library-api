# SKONGA Library API

Huduma ya ndani ya maarifa ya kielimu, inayotumiwa na **SKONGA AI backend pekee**.

> ⚠️ Hii si API ya umma. Hakuna API key za watu wa nje. Client (APK/browser) hairuhusiwi kuwasiliana na API hii moja kwa moja.

---

## Muundo wa haraka

```
SKONGA AI Backend (Render)
    │ Authorization: Bearer <SERVICE_TOKEN>
    ▼
SKONGA Library API  ← hapa (faili hizi)
    │
    ├── Postgres/Supabase  (subjects, topics, full-text search)
    └── Redis (optional)   (caching)
```

---

## Kuanzisha (Local Development)

### Hatua 1 — Mahitaji

```bash
pkg install python nodejs  # Termux
# au
brew install python         # Mac
```

### Hatua 2 — Tengeneza virtual environment na sakinisha packages

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Hatua 3 — Weka .env

```bash
cp .env.example .env
nano .env
```

Jaza:
- `DATABASE_URL` — Supabase connection string
- `SERVICE_TOKEN_HASH` — hash ya token yako (maelekezo hapa chini)

### Hatua 4 — Tengeneza token na hash yake

```bash
# 1. Tengeneza token (hifadhi hii kwa usalama — itakwenda kwenye AI Backend)
python3 -c "import secrets; print(secrets.token_hex(32))"

# 2. Hash yake (hii ndiyo inakwenda kwenye .env ya Library API)
python3 -c "import hashlib; print(hashlib.sha256(b'WEKA_TOKEN_YAKO_HAPA').hexdigest())"
```

### Hatua 5 — Tengeneza database schema

```bash
# Njia ya haraka — run SQL moja kwa moja kwenye Supabase SQL Editor:
# nakili yaliyomo ya app/db/migrations/initial_schema.sql

# au kwa programu:
python3 -c "
from app.db.models import Base
from app.db.session import engine
Base.metadata.create_all(bind=engine)
print('Schema created')
"
```

### Hatua 6 — Ingiza maudhui (kutoka SKONGA Library repo)

**Njia A — Subjects.json (skonga-library v0.07 flat layout) — inapendekezwa sasa:**

```bash
python3 ingestion/sync_from_subjects_json.py --content-dir /path/to/skonga-library
# au dry-run:
python3 ingestion/sync_from_subjects_json.py --content-dir /path/to/skonga-library --dry-run
```

Script hii inasoma `Subjects.json` + `Subjects/*.json` (+ `markdown/` kama notes) na inaandika Postgres.

**Njia B — nested content/subjects/... (meta.json layout ya zamani):**

```bash
python3 ingestion/sync_from_git.py --content-dir /njia/ya/skonga-library/content
```

### Hatua 7 — Endesha server

```bash
uvicorn app.main:app --reload
```

API itakuwepo kwa: `http://localhost:8000`
Docs (development tu): `http://localhost:8000/docs`

---

## Deploy kwenye Render

1. Tengeneza **Web Service** mpya kwenye Render
2. Unganisha repo hii
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2`
5. Ongeza Environment Variables:
   - `DATABASE_URL` (Supabase)
   - `SERVICE_TOKEN_HASH`
   - `ENVIRONMENT=production`
   - `REDIS_URL` (optional)
6. Health check path: `/health`

---

## Endpoints

Zote chini ya `/internal/v1/` — zinahitaji `Authorization: Bearer <token>`

| Method | Path | Maelezo |
|--------|------|---------|
| `GET` | `/health` | Liveness check (hauhitaji token) |
| `GET` | `/ready` | DB reachability check |
| `GET` | `/internal/v1/subjects` | Masomo yote |
| `GET` | `/internal/v1/subjects/{id}` | Somo moja |
| `GET` | `/internal/v1/subjects/{id}/forms/{form}/topics` | Mada za somo+kidato |
| `GET` | `/internal/v1/topics/{topic_id}` | Mada moja kamili |
| `POST` | `/internal/v1/search` | Utafutaji wa keyword |
| `POST` | `/internal/v1/rag/context` | **Endpoint kuu ya AI** |

---

## Jinsi ya kuunganisha na SKONGA AI Backend

Kwenye SKONGA AI Backend (Node.js/Render), ongeza:

```javascript
// .env ya AI Backend
LIBRARY_API_URL=https://your-library-api.onrender.com
LIBRARY_SERVICE_TOKEN=the_actual_token_you_generated  // siyo hash

// Kabla ya kila LLM call:
async function getLibraryContext(query, subjectHint, formHint) {
  const res = await fetch(`${process.env.LIBRARY_API_URL}/internal/v1/rag/context`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.LIBRARY_SERVICE_TOKEN}`,
    },
    body: JSON.stringify({
      query,
      subject_hint: subjectHint || null,
      form_hint: formHint || null,
      top_k: 5,
    }),
  });
  return await res.json(); // { context_text, citations, ... }
}
```

Kisha `context_text` inaingia kwenye system prompt ya LLM:

```javascript
const library = await getLibraryContext(userMessage, ...);
const systemPrompt = `You are SKONGA AI...

${library.context_text}`;  // ← maarifa ya mtaala yanaingia hapa
```

---

## Majaribio (Tests)

```bash
# Security tests (zinahitaji Python tu, hazihitaji server au DB)
python3 tests/test_security.py
```

---

## Kuzungusha Token (Token Rotation)

Kila baada ya miezi 3-6:
1. Tengeneza token mpya: `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. Hash yake: `python3 -c "import hashlib; print(hashlib.sha256(b'NEW_TOKEN').hexdigest())"`
3. Sasisha `SERVICE_TOKEN_HASH` kwenye Render (Library API)
4. Sasisha `LIBRARY_SERVICE_TOKEN` kwenye Render (AI Backend)
5. Futa token ya zamani
