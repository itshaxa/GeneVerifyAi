# GeneVerify AI — backend image (Step 11: deployment)
#
# Minimal on purpose: one FastAPI process, SQLite on a mounted volume, uploaded
# documents in a writable directory, configuration through the environment only.
# No secret is ever committed to an image layer (see .dockerignore).
#
#   docker build -t geneverify-api ./backend
#   docker run -p 8000:8000 -v geneverify-data:/srv/geneverify/data \
#     -e JWT_SECRET_KEY="<strong random secret>" \
#     -e CORS_ORIGINS="https://your-frontend.example" \
#     -e AI_PROVIDER=qwen -e QWEN_API_KEY="<key from the platform secret store>" \
#     geneverify-api
#
# The image defaults to APP_ENV=production, which refuses to boot with the
# insecure development JWT secret (app/main.py). Override APP_ENV only for a
# local trial run.

# The suite is verified on Python 3.14 (the version in backend/.venv); the app
# itself only needs 3.11+. Pin the same major/minor you test against.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv/geneverify

# Runtime dependencies only — pytest/httpx live in requirements-dev.txt.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Application code (no .env, no local database, no storage: .dockerignore).
COPY run.py ./
COPY app ./app

# Writable locations for the SQLite file and uploaded documents; mount a volume
# at /srv/geneverify/data so a redeploy never recreates/reset the database.
RUN useradd --create-home --uid 10001 geneverify \
    && mkdir -p /srv/geneverify/data/documents \
    && chown -R geneverify:geneverify /srv/geneverify
USER geneverify

ENV APP_ENV=production \
    DEBUG=false \
    HOST=0.0.0.0 \
    PORT=8000 \
    DATABASE_URL=sqlite:////srv/geneverify/data/geneverify.db \
    DOCUMENT_STORAGE_PATH=/srv/geneverify/data/documents

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health' % os.environ.get('PORT','8000')).status == 200 else 1)"

CMD ["python", "run.py"]
