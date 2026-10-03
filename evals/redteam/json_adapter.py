"""
JSON <-> SSE adapter so garak's RestGenerator can target the Trinity agent.

garak expects a JSON response with a text field; the agent streams SSE. This
tiny server bridges the two.

Usage:
    set TRINITY_API_URL=http://localhost:8001
    set TRINITY_JWT=<access token>
    python evals/redteam/json_adapter.py --port 8010

Then run garak against it (see garak_rest.json):
    garak --target_type rest -G evals/redteam/garak_rest.json \
          --probes promptinject,dan,encoding
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from agent_client import chat


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            data = {}

        message = data.get("message") or data.get("text") or ""
        result = chat(message)

        body = json.dumps(
            {"text": result.text, "write_tools": result.write_tools}
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep garak output clean
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    print(f"JSON adapter listening on http://localhost:{args.port}/scan")
    HTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
