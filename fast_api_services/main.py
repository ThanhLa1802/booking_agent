from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .routers import catalog, bookings, agent as agent_router, scheduling as scheduling_router

logger = logging.getLogger(__name__)


def _setup_langsmith(settings) -> None:
    """Configure LangSmith tracing from settings. No-op if API key not set."""
    key = settings.langchain_api_key
    if not key or key in ("your-langsmith-api-key-here", ""):
        return
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_API_KEY"] = key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
    if settings.langchain_tracing_v2 == "true":
        logger.info(
            "LangSmith tracing enabled — project: %s", settings.langchain_project
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: configure LangSmith tracing
    settings = get_settings()
    _setup_langsmith(settings)

    # Index RAG documents (skips if already indexed)
    try:
        from .agent.llm import get_embeddings
        from .agent.rag import index_docs
        embeddings = get_embeddings()
        docs_dir = Path(settings.docs_dir)
        indexed = index_docs(docs_dir, embeddings, settings.chroma_persist_dir)
        if indexed:
            logger.info("RAG: indexed %d chunks.", indexed)
    except Exception as exc:
        logger.warning("RAG startup indexing skipped: %s", exc)

    yield

    # Shutdown: close Redis connection
    from .services.slot_cache import _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Trinity Exam — Read & Agent API",
        version="0.1.0",
        lifespan=lifespan,
        redirect_slashes=False,  # prevent 307 redirects that drop Authorization header
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(catalog.router, prefix="/api")
    app.include_router(bookings.router, prefix="/api")
    app.include_router(agent_router.router, prefix="/api")
    app.include_router(scheduling_router.router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
