"""
SKONGA Library API — Health Endpoints
========================================
/health  — liveness (are we running?)
/ready   — readiness (can we serve requests? DB reachable?)

No authentication required — these are called by Render's health
checker and UptimeRobot without a token.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", include_in_schema=False)
def liveness():
    """Render uses this to know whether to restart the container."""
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.VERSION}


@router.get("/ready", include_in_schema=False)
def readiness(db: Session = Depends(get_db)):
    """
    Checks that the database is reachable. Returns 503 if not,
    so Render/load-balancer knows not to route traffic here yet.
    """
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    if not db_ok:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database is not ready")

    return {"status": "ready", "database": "ok"}
