from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    secret_key: str = "dev-secret-key-change-in-production-1234567890abcdef"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trinity_dev"
    redis_url: str = "redis://localhost:6379/0"
    django_service_url: str = "http://localhost:8000"
    cors_origins: list[str] = ["http://localhost:3000"]
    jwt_algorithm: str = "HS256"

    # AI / LLM
    llm_provider: str = "openai"          # "ollama" | "google" | "openai"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str = ""
    chroma_persist_dir: str = "./chromadb_data"
    docs_dir: str = "../docs"

    # LangSmith tracing (optional — set LANGCHAIN_API_KEY to enable)
    langchain_tracing_v2: str = "false"   # "true" to enable
    langchain_api_key: str = ""
    langchain_project: str = "trinity-ai"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
