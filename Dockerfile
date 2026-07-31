# SKONGA Library API — Dockerfile
# Multi-stage build: keeps the final image lean by separating
# dependency installation (builder) from the runtime image.

# ── Stage 1: Install Python dependencies ──────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install dependencies to a local user path (avoids running as root in prod)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime image ────────────────────────────────────────────────
FROM python:3.12-slim

# Non-root user for security
RUN groupadd -r skonga && useradd -r -g skonga skonga

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/skonga/.local
ENV PATH=/home/skonga/.local/bin:$PATH

# Copy application source
COPY app/ ./app/
COPY ingestion/ ./ingestion/

# Run as non-root
USER skonga

EXPOSE 8000

# Uvicorn with 2 workers — tune upward if moving to a larger Render plan
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
