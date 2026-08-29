"""FastAPI application entry point.

Run it with:
    uvicorn app.main:app --reload --port 8000

Interactive API docs are then at http://localhost:8000/docs — useful in a
demo, because you can show every endpoint and its role requirement live.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import settings
from app.db.session import engine

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Decision support API for Gram Panchayat administration: citizen "
        "records, welfare schemes, grievances, development projects, Gram "
        "Sabha minutes and analytics."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Database problems become a clear 503 rather than a stack trace.

    The previous frontend swallowed sync failures into console warnings, so a
    broken database looked like a working app. Failures are loud here.
    """
    log.exception("Database error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "The database is unavailable. The change was not saved."},
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness plus the two facts the frontend needs at startup: is the
    database reachable, and is the language model configured."""
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "aiEnabled": settings.ai_enabled,
        "version": app.version,
    }
