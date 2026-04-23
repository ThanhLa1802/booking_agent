"""
LLM + Embeddings interface.
Business logic and tools always call get_llm() / get_embeddings() — never hardcode
ChatOllama directly. This allows swapping to Google Gemini or GPT-4o in production
by changing LLM_PROVIDER in .env only.

All LangChain imports are lazy to avoid torch/numpy BLAS crash on Windows.
"""
from fast_api_services.config import get_settings


def get_llm():
    """Return the configured LLM (BaseChatModel). Imports are lazy."""
    settings = get_settings()
    provider = getattr(settings, "llm_provider", "ollama")
    model = getattr(settings, "llm_model", "llama3.1:8b")

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, temperature=0)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, temperature=0)
    else:  # default: ollama (local dev)
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, temperature=0)


def get_embeddings():
    """Return the configured Embeddings. Imports are lazy.
    Provider is inferred from llm_provider:
      openai  → OpenAIEmbeddings (text-embedding-3-small by default)
      google  → GoogleGenerativeAIEmbeddings
      ollama  → OllamaEmbeddings (nomic-embed-text, local)
    """
    settings = get_settings()
    provider = getattr(settings, "llm_provider", "ollama")
    model = getattr(settings, "embedding_model", "nomic-embed-text")

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model)
    elif provider == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(model=model)
    else:  # ollama (local dev)
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(model=model)
