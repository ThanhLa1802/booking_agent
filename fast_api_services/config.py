from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "dev-secret-key-change-in-production-1234567890abcdef"


class Settings(BaseSettings):
    secret_key: str = _DEFAULT_SECRET

    @model_validator(mode="after")
    def _reject_default_secret(self) -> "Settings":
        if self.secret_key == _DEFAULT_SECRET:
            raise ValueError(
                "SECRET_KEY is set to the insecure default value. "
                "Set a strong SECRET_KEY in your .env file before starting the server."
            )
        return self
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
