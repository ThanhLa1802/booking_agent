from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .routers import catalog, bookings, agent as agent_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: index RAG documents (skips if already indexed)
    settings = get_settings()
    try:
        from .agent.llm import get_embeddings
        from .agent.rag import index_docs
        embeddings = get_embeddings()
        docs_dir = Path(settings.docs_dir)
        indexed = index_docs(docs_dir, embeddings, settings.chroma_persist_dir)
        if indexed:
            import logging
            logging.getLogger(__name__).info("RAG: indexed %d chunks.", indexed)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("RAG startup indexing skipped: %s", exc)

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

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
