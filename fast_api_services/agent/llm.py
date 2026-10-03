"""
LLM + Embeddings interface.

Business logic and tools always call get_llm() / get_embeddings() — never hardcode
ChatOllama directly. This allows swapping to Google Gemini or GPT-4o in production
by changing LLM_PROVIDER in .env only.

Resilience:
  * get_llm()            — primary chat model with timeout + retries where supported.
  * get_classifier_llm() — structured-output classifier (TaskType) with retry and an
                           optional fallback model. Returns None when structured
                           output is unavailable so callers can fall back to text.

All LangChain imports are lazy to avoid torch/numpy BLAS crash on Windows.
"""
from fast_api_services.config import get_settings


def _build_chat(provider: str, model: str):
    """Construct a provider chat model, applying timeout/retries where supported."""
    settings = get_settings()
    timeout = getattr(settings, "llm_timeout_seconds", 30)
    retries = getattr(settings, "llm_max_retries", 2)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        try:
            return ChatGoogleGenerativeAI(model=model, temperature=0, timeout=timeout)
        except TypeError:  # older signature without timeout
            return ChatGoogleGenerativeAI(model=model, temperature=0)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model, temperature=0, timeout=timeout, max_retries=retries
        )
    else:  # default: ollama (local dev)
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, temperature=0)


def get_llm():
    """Return the configured primary LLM (BaseChatModel). Imports are lazy."""
    settings = get_settings()
    provider = getattr(settings, "llm_provider", "ollama")
    model = getattr(settings, "llm_model", "llama3.1:8b")
    return _build_chat(provider, model)


def get_classifier_llm():
    """
    Return a Runnable that maps messages → ``TaskType`` (structured output).

    Wraps the primary model with retries and an optional fallback model. Returns
    None if the provider/model does not support structured output — callers must
    then fall back to text classification.
    """
    from .state import TaskType

    settings = get_settings()
    try:
        primary = get_llm().with_structured_output(TaskType)
    except Exception:
        return None

    retries = getattr(settings, "llm_max_retries", 2)
    try:
        primary = primary.with_retry(stop_after_attempt=retries + 1)
    except Exception:
        pass

    fb_provider = getattr(settings, "llm_fallback_provider", "")
    fb_model = getattr(settings, "llm_fallback_model", "")
    if fb_provider and fb_model:
        try:
            fallback = _build_chat(fb_provider, fb_model).with_structured_output(TaskType)
            primary = primary.with_fallbacks([fallback])
        except Exception:
            pass
    return primary


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
