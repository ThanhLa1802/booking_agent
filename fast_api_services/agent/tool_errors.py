"""
Make tool argument/execution errors non-fatal so the agent can self-correct.

A tool called with missing or invalid arguments raises a pydantic
``ValidationError`` while parsing its input. By default that aborts the whole
agent turn (the user gets an empty reply). langchain-core 0.3.x lets a tool
convert such an error into a normal observation (``handle_validation_error`` /
``handle_tool_error``), which is fed back to the model so it can retry with the
correct arguments — no side effect, no crashed turn.

This is a robustness layer only; it never grants a write (see
``authorization.authorize_write``).
"""
from __future__ import annotations


def _validation_message(error) -> str:
    return (
        f"Tool argument error: {error} "
        "Call the tool again with all required arguments, or ask the user for "
        "the missing value."
    )


def _tool_message(error) -> str:
    return f"Tool failed: {error}. You may retry or inform the user."


def harden_tools(tools: list) -> list:
    """Convert tool argument/execution errors into observations (returns *tools*)."""
    for t in tools:
        try:
            t.handle_validation_error = _validation_message
            t.handle_tool_error = _tool_message
        except Exception:  # best-effort; never break tool construction
            pass
    return tools
