"""
SKONGA Library API — Main Application
========================================
FastAPI entrypoint. Registers all routers under /internal/v1/.

Security note: CORS is deliberately NOT configured.
This service is internal-only. The Android/Web client must NEVER
call this API directly — only SKONGA AI Backend can, using its
SERVICE_TOKEN. Absence of CORS headers means any browser or
WebView request will be refused at the preflight stage automatically.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.api.v1 import health, subjects, topics, search, rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the app.

    Startup verifies the database is reachable before accepting traffic.
    If the database is not reachable we raise to prevent the process from
    starting and accepting requests. This aligns with the readiness probe
    behaviour in /ready.
    """
    from app.db.session import engine
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connected")
    except Exception as e:
        # Fail fast so the process doesn't accept traffic when DB is down
        print(f"⚠️ Database connection failed: {e}")
        raise

    yield
    # Shutdown: nothing special needed for Phase 1


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    # Docs are available in development; disabled in production to reduce
    # exposure (an internal API doesn't need a public-facing Swagger page).
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# Compress responses larger than 1KB — helpful for large subject lists
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Register routers ────────────────────────────────────────────────────────
API_PREFIX = "/internal/v1"

# health has its own paths (e.g. /health, /ready) and should be mounted without
# the API prefix so external platform health checks keep working.
app.include_router(health.router)                          # /health, /ready
app.include_router(subjects.router, prefix=API_PREFIX)     # /internal/v1/subjects
app.include_router(topics.router,   prefix=API_PREFIX)     # /internal/v1/topics
app.include_router(search.router,   prefix=API_PREFIX)     # /internal/v1/search
app.include_router(rag.router,      prefix=API_PREFIX)     # /internal/v1/rag/context
