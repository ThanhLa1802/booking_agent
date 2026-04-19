"""
LangChain ReAct agent factory for the Trinity exam booking assistant.

The agent is stateless per-request; conversation history is loaded from Redis
and injected as chat_history in the prompt.
"""
from __future__ import annotations

# Heavy langchain imports are lazy to avoid torch/numpy BLAS crash on import

SYSTEM_PROMPT = """\
You are Trinity Exam Assistant — a helpful, knowledgeable advisor for Trinity College \
London music exam bookings in Vietnam.

You help students (Grade 1–8) and their parents to:
- Understand the exam syllabus (Classical & Jazz, Rock & Pop, Theory of Music)
- Choose the right grade and instrument
- Find available exam slots and centers
- Book, view, or cancel exams

RULES:
1. Before calling create_booking or cancel_booking, ALWAYS summarise the details \
and ask the user to confirm explicitly.
2. Set confirm=True ONLY after the user replies with clear confirmation \
("yes", "xác nhận", "đồng ý", or equivalent).
3. Never assume confirmation — a vague reply is NOT confirmation.
4. Respond in Vietnamese if the user writes in Vietnamese; otherwise respond in English.
5. You have a maximum of 5 tool calls per conversation turn — be efficient.
6. If you cannot help with something, say so clearly rather than guessing.
7. Keep responses concise and focused; avoid unnecessary repetition.
"""


def _build_prompt():
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )


def create_agent(llm, tools: list, chat_history=None):
    """
    Create a ReAct AgentExecutor.
    chat_history is injected per-request from Redis-backed memory.
    """
    from langchain.agents import AgentExecutor, create_react_agent  # lazy

    prompt = _build_prompt()
    agent = create_react_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=5,
        handle_parsing_errors=True,
        verbose=False,
    )
