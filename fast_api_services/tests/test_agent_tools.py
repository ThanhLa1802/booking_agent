"""
Tests for agent tools — especially the confirmation gate pattern.

No real DB, Redis, or Ollama needed: everything is mocked.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fast_api_services.agent.tools import ToolContext, make_tools, _CONFIRM_REQUIRED


@pytest.fixture
def mock_ctx():
    ctx = MagicMock(spec=ToolContext)
    ctx.db = AsyncMock()
    ctx.redis = AsyncMock()
    ctx.user_id = 42
    ctx.user_token = "test.jwt.token"
    ctx.session_factory = MagicMock()
    ctx.embeddings = MagicMock()
    ctx.persist_dir = "./test_chroma"
    ctx.user_role = "STUDENT"
    return ctx


# ── Confirmation gate tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_booking_requires_confirm(mock_ctx):
    """create_booking with confirm=False must return warning, not attempt booking."""
    tools = make_tools(mock_ctx)
    create_booking_tool = next(t for t in tools if t.name == "create_booking")

    result = await create_booking_tool.ainvoke({
        "slot_id": 1,
        "student_name": "Nguyen Van A",
        "student_dob": "2010-01-01",
        "notes": "",
        "confirm": False,
    })

    assert _CONFIRM_REQUIRED in result
    assert "Slot 1" in result
    assert "Nguyen Van A" in result


@pytest.mark.asyncio
async def test_cancel_booking_requires_confirm(mock_ctx):
    """cancel_booking with confirm=False must return warning, not attempt cancellation."""
    tools = make_tools(mock_ctx)
    cancel_tool = next(t for t in tools if t.name == "cancel_booking")

    result = await cancel_tool.ainvoke({
        "booking_id": 99,
        "reason": "schedule conflict",
        "confirm": False,
    })

    assert _CONFIRM_REQUIRED in result
    assert "99" in result


@pytest.mark.asyncio
async def test_create_booking_with_confirm_calls_django(mock_ctx):
    """create_booking confirm=True should call Django service."""
    import httpx

    tools = make_tools(mock_ctx)
    create_booking_tool = next(t for t in tools if t.name == "create_booking")

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": 123}

    with patch("fast_api_services.agent.tools.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await create_booking_tool.ainvoke({
            "slot_id": 5,
            "student_name": "Le Thi B",
            "student_dob": "2012-06-15",
            "notes": "needs piano",
            "confirm": True,
        })

    assert "123" in result
    assert "Le Thi B" in result
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_booking_with_confirm_calls_django(mock_ctx):
    """cancel_booking confirm=True should call Django cancel endpoint."""
    tools = make_tools(mock_ctx)
    cancel_tool = next(t for t in tools if t.name == "cancel_booking")

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("fast_api_services.agent.tools.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await cancel_tool.ainvoke({
            "booking_id": 7,
            "reason": "changed plans",
            "confirm": True,
        })

    assert "7" in result
    assert "cancelled" in result.lower()


# ── Read tools (no side effects) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_my_bookings_no_bookings(mock_ctx):
    """list_my_bookings returns friendly message when user has no bookings."""
    with patch(
        "fast_api_services.agent.tools.list_user_bookings",
        new=AsyncMock(return_value=[]),
    ):
        tools = make_tools(mock_ctx)
        t = next(t for t in tools if t.name == "list_my_bookings")
        result = await t.ainvoke({})

    assert "no bookings" in result.lower()


@pytest.mark.asyncio
async def test_search_exam_docs_calls_rag(mock_ctx):
    """search_exam_docs should delegate to rag.search_docs."""
    with patch(
        "fast_api_services.agent.tools._search_docs",
        return_value=["Grade 5 Theory is mandatory for higher grades."],
    ):
        tools = make_tools(mock_ctx)
        t = next(t for t in tools if t.name == "search_exam_docs")
        result = await t.ainvoke({"query": "Grade 5 Theory", "doc_type": "syllabus"})

    assert "Grade 5" in result


@pytest.mark.asyncio
async def test_search_exam_docs_no_results(mock_ctx):
    """search_exam_docs returns 'No relevant documents found' on empty RAG results."""
    with patch(
        "fast_api_services.agent.tools._search_docs",
        return_value=[],
    ):
        tools = make_tools(mock_ctx)
        t = next(t for t in tools if t.name == "search_exam_docs")
        result = await t.ainvoke({"query": "unknown topic"})

    assert "No relevant" in result


# ── Tool count ────────────────────────────────────────────────────────────────

def test_make_tools_returns_seven(mock_ctx):
    """make_tools must return exactly 9 tools (7 booking + 2 reschedule)."""
    tools = make_tools(mock_ctx)
    assert len(tools) == 9


def test_tool_names(mock_ctx):
    """All expected tool names are present."""
    tools = make_tools(mock_ctx)
    names = {t.name for t in tools}
    expected = {
        "search_exam_docs",
        "list_courses",
        "list_available_slots",
        "get_booking_detail",
        "list_my_bookings",
        "create_booking",
        "cancel_booking",
        "suggest_slots_for_reschedule",
        "reschedule_booking",
    }
    assert expected == names
