"""
Tests for POST /api/agent/chat — SSE endpoint.

The LangChain agent is fully mocked; no Ollama needed.
"""
import json
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

# ── helpers ───────────────────────────────────────────────────────────────────

def _make_fake_token_event(text: str):
    return {
        "event": "on_chat_model_stream",
        "name": "ChatModel",
        "data": {"chunk": MagicMock(content=text)},
    }


def _make_fake_done_event(output: str):
    return {
        "event": "on_chain_end",
        "name": "AgentExecutor",
        "data": {"output": {"output": output}},
    }


async def _fake_stream(events):
    for e in events:
        yield e


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def authed_client(fake_redis):
    """AsyncClient with auth dependency overridden."""
    from fast_api_services.main import app
    from fast_api_services.auth import get_current_user
    from fast_api_services.database import get_db

    async def override_user():
        return {"user_id": 1, "email": "test@example.com", "role": "STUDENT"}

    mock_db = AsyncMock()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    yield app, fake_redis, mock_db

    app.dependency_overrides.clear()


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_endpoint_returns_sse_events(authed_client, fake_redis):
    """POST /api/agent/chat should return SSE events."""
    app, _, _ = authed_client

    events = [
        _make_fake_token_event("Xin chào"),
        _make_fake_token_event("! Tôi có thể giúp gì?"),
        _make_fake_done_event("Xin chào! Tôi có thể giúp gì?"),
    ]
    fake_executor = MagicMock()
    fake_executor.astream_events = MagicMock(return_value=_fake_stream(events))

    with (
        patch("fast_api_services.agent.llm.get_llm", return_value=MagicMock()),
        patch("fast_api_services.agent.llm.get_embeddings", return_value=MagicMock()),
        patch("fast_api_services.agent.tools.make_tools", return_value=[]),
        patch("fast_api_services.agent.memory.load_history", new=AsyncMock(return_value=[])),
        patch("fast_api_services.agent.memory.save_history", new=AsyncMock()),
        patch("fast_api_services.agent.agent.create_agent", return_value=fake_executor),
        patch(
            "fast_api_services.services.slot_cache.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                "/api/agent/chat",
                json={"message": "xin chào"},
                headers={"Authorization": "Bearer testtoken"},
            ) as response:
                assert response.status_code == 200
                content_type = response.headers.get("content-type", "")
                assert "text/event-stream" in content_type

                raw = await response.aread()
                text = raw.decode()

    # Should contain at least one data: line
    assert "data:" in text


@pytest.mark.asyncio
async def test_chat_endpoint_emits_done_event(authed_client, fake_redis):
    """The 'done' event should appear in the SSE stream with the final answer."""
    app, _, _ = authed_client
    final_answer = "Đây là câu trả lời cuối."

    events = [_make_fake_done_event(final_answer)]
    fake_executor = MagicMock()
    fake_executor.astream_events = MagicMock(return_value=_fake_stream(events))

    with (
        patch("fast_api_services.agent.llm.get_llm", return_value=MagicMock()),
        patch("fast_api_services.agent.llm.get_embeddings", return_value=MagicMock()),
        patch("fast_api_services.agent.tools.make_tools", return_value=[]),
        patch("fast_api_services.agent.memory.load_history", new=AsyncMock(return_value=[])),
        patch("fast_api_services.agent.memory.save_history", new=AsyncMock()),
        patch("fast_api_services.agent.agent.create_agent", return_value=fake_executor),
        patch(
            "fast_api_services.services.slot_cache.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                "/api/agent/chat",
                json={"message": "test"},
                headers={"Authorization": "Bearer testtoken"},
            ) as response:
                raw = await response.aread()

    text = raw.decode()
    # Find and parse the done event
    done_data = None
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = json.loads(line[len("data:"):].strip())
            if payload.get("type") == "done":
                done_data = payload
                break

    assert done_data is not None
    assert done_data["content"] == final_answer


@pytest.mark.asyncio
async def test_chat_requires_auth():
    """POST /api/agent/chat without valid auth should return 401."""
    from fast_api_services.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/agent/chat",
            json={"message": "hello"},
        )
    assert response.status_code in (401, 403)  # FastAPI returns 403 when no token


@pytest.mark.asyncio
async def test_chat_empty_message_rejected(authed_client):
    """Empty message string should be rejected (422)."""
    app, _, _ = authed_client

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/agent/chat",
            json={"message": ""},
            headers={"Authorization": "Bearer testtoken"},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_saves_history_after_done(authed_client, fake_redis):
    """save_history should be called once after the AgentExecutor finishes."""
    app, _, _ = authed_client
    save_mock = AsyncMock()

    events = [_make_fake_done_event("Done!")]
    fake_executor = MagicMock()
    fake_executor.astream_events = MagicMock(return_value=_fake_stream(events))

    with (
        patch("fast_api_services.agent.llm.get_llm", return_value=MagicMock()),
        patch("fast_api_services.agent.llm.get_embeddings", return_value=MagicMock()),
        patch("fast_api_services.agent.tools.make_tools", return_value=[]),
        patch("fast_api_services.agent.memory.load_history", new=AsyncMock(return_value=[])),
        patch("fast_api_services.agent.memory.save_history", new=save_mock),
        patch("fast_api_services.agent.agent.create_agent", return_value=fake_executor),
        patch(
            "fast_api_services.services.slot_cache.get_redis_client",
            new=AsyncMock(return_value=fake_redis),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            async with client.stream(
                "POST",
                "/api/agent/chat",
                json={"message": "test history"},
                headers={"Authorization": "Bearer testtoken"},
            ) as response:
                await response.aread()

    save_mock.assert_called_once()
