"""
FastAPI application entry point for the HR Multi-Agent Router.

Features:
    - CORS middleware for cross-origin requests
    - Lifespan events for DB initialization on startup
    - Global exception handler (polite responses, no raw stack traces)
    - Automatic OpenAPI documentation at /docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import get_settings
from database import init_db
from routers.api import router as api_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-25s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, cleanup on shutdown."""
    logger.info("Starting HR Multi-Agent Router...")
    await init_db()
    logger.info("Database initialized. Server is ready.")
    yield
    logger.info("Shutting down HR Multi-Agent Router.")


app = FastAPI(
    title="HR Multi-Agent Router",
    description=(
        "A multi-agent task routing and memory engine for HR automation. "
        "Routes natural language HR requests to specialized sub-agents "
        "(Scheduling, Leave, Compliance) with a two-tier memory system "
        "(STM/LTM) and append-only audit logging."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

app.mount("/dashboard", StaticFiles(directory="static", html=True), name="dashboard")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler that returns polite error messages.

    NEVER exposes raw Python stack traces to the end user.
    All errors are logged server-side for debugging.
    """
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": (
                "We apologize, but something went wrong while processing "
                "your request. Our team has been notified. Please try again "
                "in a moment, or contact HR directly at hr@company.com."
            ),
        },
    )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — redirects to the interactive dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


@app.get("/api/v1/info", tags=["Root"])
async def api_info():
    """API information and available endpoints."""
    return {
        "service": "HR Multi-Agent Router",
        "version": "1.0.0",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "endpoints": {
            "process_request": "POST /api/v1/request",
            "audit_logs": "GET /api/v1/audit",
            "user_memory": "GET /api/v1/memory/{user_id}",
            "clear_stm": "DELETE /api/v1/memory/{user_id}",
            "health": "GET /api/v1/health",
        },
    }



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
