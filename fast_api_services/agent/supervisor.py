"""
SupervisorGraph — top-level LangGraph router.

Routes each conversation turn to the appropriate sub-graph based on user_role:
    CENTER_ADMIN → SchedulingGraph
    STUDENT / PARENT → BookingGraph

Graph topology:
    START → route_node → (CENTER_ADMIN) → scheduling_subgraph → END
                       → (STUDENT/PARENT) → booking_subgraph  → END

The checkpointer stores state in Redis keyed by `thread_id = user_id`,
enabling human-in-the-loop resume for SchedulingGraph (the graph can
pause at confirm_node and resume when the admin sends "xác nhận").
"""
from __future__ import annotations

from .state import BookingState, SchedulingState


# ── routing function ──────────────────────────────────────────────────────────

def _route_by_role(state: dict) -> str:
    role = state.get("user_role", "STUDENT")
    if role == "CENTER_ADMIN":
        return "scheduling_subgraph"
    return "booking_subgraph"


# ── factory ───────────────────────────────────────────────────────────────────

def create_supervisor_graph(
    booking_tools: list,
    scheduling_tools: list,
    llm,
    chat_history: list,
    checkpointer=None,
):
    """
    Build and compile the SupervisorGraph.

    Args:
        booking_tools: Tools for the BookingGraph (student/parent agent).
        scheduling_tools: Tools for the SchedulingGraph (admin agent).
        llm: LLM instance (from get_llm()).
        chat_history: Conversation history loaded from Redis.
        checkpointer: Optional LangGraph checkpointer for state persistence.
    Returns:
        Compiled CompiledGraph ready for ainvoke / astream_events.
    """
    from langgraph.graph import END, START, StateGraph

    from .booking_graph import create_booking_graph
    from .scheduling_graph import create_scheduling_graph

    # ── build sub-graphs ──────────────────────────────────────────────────────
    booking_graph = create_booking_graph(booking_tools, llm, chat_history)
    scheduling_graph = create_scheduling_graph(scheduling_tools, llm, checkpointer)

    # ── supervisor state: superset of both sub-graph states ──────────────────
    # We use a plain dict-based state to be role-agnostic at the router level.
    # sub-graphs are compiled separately and called as nodes.

    async def booking_subgraph_node(state: dict) -> dict:
        result = await booking_graph.ainvoke(
            BookingState(messages=state["messages"], user_role=state["user_role"])
        )
        return {"messages": result["messages"]}

    async def scheduling_subgraph_node(state: dict) -> dict:
        sched_state = SchedulingState(
            messages=state["messages"],
            user_role=state["user_role"],
            task_type=state.get("task_type", "general"),
            proposal=state.get("proposal"),
            confirmed=state.get("confirmed", False),
        )
        result = await scheduling_graph.ainvoke(
            sched_state,
            config={"configurable": {"thread_id": state.get("thread_id", "default")}},
        )
        return {
            "messages": result["messages"],
            "task_type": result.get("task_type", "general"),
            "proposal": result.get("proposal"),
            "confirmed": result.get("confirmed", False),
        }

    # ── supervisor graph ──────────────────────────────────────────────────────
    from langgraph.graph import StateGraph as SG
    from typing_extensions import TypedDict
    from typing import Annotated, Optional
    from langgraph.graph.message import add_messages

    class SupervisorState(TypedDict):
        messages: Annotated[list, add_messages]
        user_role: str
        task_type: str
        proposal: Optional[dict]
        confirmed: bool
        thread_id: str

    builder = SG(SupervisorState)
    builder.add_node("booking_subgraph", booking_subgraph_node)
    builder.add_node("scheduling_subgraph", scheduling_subgraph_node)

    builder.add_conditional_edges(START, _route_by_role)
    builder.add_edge("booking_subgraph", END)
    builder.add_edge("scheduling_subgraph", END)

    return builder.compile(checkpointer=checkpointer)
