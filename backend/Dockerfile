# ── Backend image: FastAPI + Knowledge Graphs + baked-in seed data ───────────
# Build context is the REPO ROOT (see docker-compose.yml).  The seed data now
# lives inside the backend package (backend/data/) so it ships with the backend
# everywhere — Docker, local, and Vercel's services bundle.  The loader locates
# it via app.data.paths.find_data_dir() (searches ancestors for a data/ dir).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Cache the sentence-transformers model inside the image
    HF_HOME=/opt/hf-cache \
    UV_PROJECT_ENVIRONMENT=/app/backend/.venv

# uv for fast, reproducible installs from uv.lock
RUN pip install --no-cache-dir uv

WORKDIR /app/backend

# 1. Dependency layer (cached unless lockfile changes)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# NOTE: the all-MiniLM-L6-v2 embedding model is downloaded lazily on first boot
# into HF_HOME (mounted as a persistent volume in docker-compose.yml) rather
# than at build time — the BuildKit sandbox can't reliably reach huggingface.co.
# First container start takes ~30-60s while it caches the model; subsequent
# starts reuse the volume and boot fast.

# 2. Application code + seed data (backend/ already contains data/, so this
#    single copy brings both: /app/backend/{app,data,...})
COPY backend/ ./

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
