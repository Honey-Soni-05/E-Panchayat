# Backend image for Render (and anywhere else that runs a container).
#
# Slim rather than alpine: PyMuPDF ships manylinux wheels that alpine's musl
# libc cannot use, so alpine would build it from source and turn a one-minute
# deploy into a fifteen-minute one.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first, as their own layer: application code changes on every
# deploy, dependencies almost never, so this keeps the slow step cached.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects PORT and expects the process to bind it on 0.0.0.0. Binding
# 127.0.0.1 is the classic "deploy succeeded but nothing responds" mistake:
# the health check comes from outside the container.
ENV PORT=8000
EXPOSE 8000

# Migrations run at startup rather than in a build step, because the build has
# no database credentials. This is safe on a single instance; if this ever runs
# more than one replica, move it to a release command so two containers cannot
# migrate concurrently.
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2
