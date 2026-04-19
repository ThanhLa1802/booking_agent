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
    llm_provider: str = "ollama"          # "ollama" | "google" | "openai"
    llm_model: str = "llama3.1:8b"
    embedding_model: str = "nomic-embed-text"
    chroma_persist_dir: str = "./chromadb_data"
    docs_dir: str = "../docs"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
