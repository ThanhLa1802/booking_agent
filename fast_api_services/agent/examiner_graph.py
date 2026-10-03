"""
ExaminerGraph — LangGraph wrapper for the EXAMINER read-only agent.

The examiner gets a ReAct agent restricted to their own schedule. Unlike the
booking graph, there are no write tools and no confirmation gate here: every
tool is a scoped read.

Graph topology:
    START → examiner_node → END
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from .state import ExaminerState


def _make_examiner_node(tools: list, llm, chat_history: list):
    """Return an async node that runs the examiner AgentExecutor."""
    # lazy import to avoid torch/numpy BLAS crash at module load
    from .agent import EXAMINER_SYSTEM_PROMPT, create_agent

    agent_executor = create_agent(
        llm, tools, chat_history, system_prompt=EXAMINER_SYSTEM_PROMPT
    )

    async def examiner_node(state: ExaminerState) -> dict:
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

    return examiner_node


def create_examiner_graph(tools: list, llm, chat_history: list):
    """Build and compile a minimal StateGraph for the examiner schedule view."""
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(ExaminerState)
    builder.add_node("examiner_node", _make_examiner_node(tools, llm, chat_history))
    builder.add_edge(START, "examiner_node")
    builder.add_edge("examiner_node", END)
    return builder.compile()
