"""
Minimal stdlib client for the Trinity agent SSE endpoint.

Shared by the red-team runner and the garak JSON adapter so both parse the same
event stream and detect write-tool execution identically. No third-party deps.
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


class AgentResult:
    def __init__(self, text, tool_starts, tool_ends, error=None):
        self.text = text
        self.tool_starts = tool_starts
        self.tool_ends = tool_ends
        self.error = error

    @property
    def write_tools(self):
        return [t for t in self.tool_starts if t in WRITE_TOOLS]


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
    tool_ends: list[str] = []
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
                    tool_ends.append(payload.get("tool"))
                elif ptype == "error":
                    error = payload.get("content")
    except urllib.error.HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.read()[:200]!r}"
    except Exception as exc:  # noqa: BLE001
        error = f"request failed: {exc}"

    return AgentResult(text, tool_starts, tool_ends, error)
