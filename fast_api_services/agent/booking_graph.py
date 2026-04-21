"""
BookingGraph — LangGraph wrapper around the existing AgentExecutor.

This is the thin vertical slice for STUDENT / PARENT users. It preserves
100% of the existing behavior (ReAct loop, confirm gate in tools) while
participating in the SupervisorGraph routing mechanism.

Graph topology:
    START → booking_node → END
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from .state import BookingState


def _make_booking_node(tools: list, llm, chat_history: list):
    """
    Return an async node function that runs the booking AgentExecutor
    and appends the AI response to the state's message list.
    """
    # lazy import to avoid torch/numpy BLAS crash at module load
    from .agent import create_agent

    agent_executor = create_agent(llm, tools, chat_history)

    async def booking_node(state: BookingState) -> dict:
        # The last message is the user's current input
        last_human = next(
            (m for m in reversed(state["messages"]) if getattr(m, "type", None) == "human"),
            None,
        )
        user_input = last_human.content if last_human else ""

        result = await agent_executor.ainvoke(
            {"input": user_input, "chat_history": chat_history}
        )
        reply = result.get("output", "")
        return {"messages": [AIMessage(content=reply)]}

    return booking_node


def create_booking_graph(tools: list, llm, chat_history: list):
    """
    Build and compile a minimal StateGraph for the booking workflow.

    Usage:
        graph = create_booking_graph(tools, llm, chat_history)
        result = await graph.ainvoke(initial_state)
    """
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(BookingState)
    builder.add_node("booking_node", _make_booking_node(tools, llm, chat_history))
    builder.add_edge(START, "booking_node")
    builder.add_edge("booking_node", END)
    return builder.compile()
