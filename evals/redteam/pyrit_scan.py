"""
PyRIT multi-turn red-team scan against the Trinity agent.

Prereqs:
    pip install -r evals/redteam/requirements-redteam.txt
    # terminal 1 — start the JSON adapter (PyRIT's HTTPTarget expects JSON)
    set TRINITY_API_URL=http://localhost:8001
    set TRINITY_JWT=<access token>
    python evals/redteam/json_adapter.py
    # terminal 2
    python evals/redteam/pyrit_scan.py

The agent is reached through json_adapter.py because PyRIT's HTTPTarget parses a
JSON response, while the agent streams SSE.

NOTE: PyRIT's API evolves quickly. If an import/signature has moved, adjust to
the installed version — see https://microsoft.github.io/PyRIT/.
"""
from __future__ import annotations

import asyncio
import os

from attacks import ATTACKS

ADAPTER_URL = os.environ.get("TRINITY_ADAPTER_URL", "http://localhost:8010/scan")


def build_target():
    from pyrit.prompt_target import (
        HTTPTarget,
        get_http_target_json_response_callback_function,
    )

    raw_request = (
        f"POST {ADAPTER_URL}\n"
        "Content-Type: application/json\n"
        "\n"
        '{"message": "{PROMPT}"}\n'
    )
    parser = get_http_target_json_response_callback_function(key="text")
    return HTTPTarget(
        http_request=raw_request,
        callback_function=parser,
        timeout=120.0,
    )


async def main():
    from pyrit.common import IN_MEMORY, initialize_pyrit
    from pyrit.orchestrator import PromptSendingOrchestrator

    initialize_pyrit(memory_db_type=IN_MEMORY)

    target = build_target()
    prompts = [turn for attack in ATTACKS for turn in attack["turns"]]

    orchestrator = PromptSendingOrchestrator(target)
    await orchestrator.send_prompts_async(prompt_list=prompts)
    await orchestrator.print_conversations_async()


if __name__ == "__main__":
    asyncio.run(main())
