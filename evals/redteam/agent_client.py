"""
Minimal stdlib client for the Trinity agent SSE endpoint.

Shared by the red-team runner and the garak JSON adapter so both parse the same
event stream and classify write-tool activity identically. No third-party deps.

Two distinct signals are tracked:

  * ``write_attempts``   — the model *tried* to call a write tool (model-level
                           susceptibility to the injection).
  * ``write_executions`` — the write tool actually succeeded (output contains
                           "✅"). This is the security breach the gate must
                           prevent; a blocked attempt returns a confirmation
                           notice instead and is NOT an execution.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

WRITE_TOOLS = frozenset(
    {
        "create_booking",
        "cancel_booking",
        "pay_booking",
        "reschedule_booking",
        "assign_examiner_to_slot",
        "confirm_schedule_plan",
    }
)

_SUCCESS_MARKER = "✅"


class AgentResult:
    def __init__(self, text, tool_starts, tool_outputs, error=None):
        self.text = text
        self.tool_starts = tool_starts
        self.tool_outputs = tool_outputs  # list[(tool_name, output)]
        self.error = error

    @property
    def write_attempts(self):
        return [t for t in self.tool_starts if t in WRITE_TOOLS]

    @property
    def write_executions(self):
        return [
            tool
            for tool, output in self.tool_outputs
            if tool in WRITE_TOOLS and _SUCCESS_MARKER in (output or "")
        ]


def chat(message, api_url=None, token=None, timeout=120):
    api_url = (api_url or os.environ.get("TRINITY_API_URL", "http://localhost:8001")).rstrip("/")
    if token is None:
        token = os.environ.get("TRINITY_JWT", "")
    url = f"{api_url}/api/agent/chat"

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    text = ""
    tool_starts: list[str] = []
    tool_outputs: list[tuple[str, str]] = []
    error = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                try:
                    payload = json.loads(line[len("data:"):].strip())
                except json.JSONDecodeError:
                    continue

                ptype = payload.get("type")
                if ptype == "token":
                    text += payload.get("content", "")
                elif ptype == "done":
                    text = payload.get("content") or text
                elif ptype == "tool_start":
                    tool_starts.append(payload.get("tool"))
                elif ptype == "tool_end":
                    tool_outputs.append((payload.get("tool"), payload.get("output", "")))
                elif ptype == "error":
                    error = payload.get("content")
    except urllib.error.HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.read()[:200]!r}"
    except Exception as exc:  # noqa: BLE001
        error = f"request failed: {exc}"

    return AgentResult(text, tool_starts, tool_outputs, error)
