"""
Relo AI web server: serves the HTML/CSS/JS front end and one JSON endpoint for the agent.
Standard library only.  Run from the repo root:  python3 frontend/server.py   (then open http://localhost:8000)

Agent selection:
  - If agent.py exists at the repo root, its respond(messages) is used.
  - Otherwise (or with RELO_MOCK=1) the mock agent in frontend/mock_agent.py is used.
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATIC = HERE / "static"
for p in (ROOT, HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from adapter import normalize  # noqa: E402
from sample_data import SAMPLES  # noqa: E402

USE_MOCK = os.environ.get("RELO_MOCK") == "1" or not (ROOT / "agent.py").exists()
if USE_MOCK:
    from mock_agent import respond  # noqa: E402
else:
    from agent import respond  # noqa: E402,F401

MAX_BODY = 200_000


class Handler(BaseHTTPRequestHandler):
    server_version = "Relo/1.0"

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path, _, query = self.path.partition("?")
        if path == "/api/config":
            return self._json(200, {"mock": USE_MOCK})
        if path == "/api/sample":
            name = query.split("name=", 1)[1].split("&")[0] if "name=" in query else "options"
            if name not in SAMPLES:
                return self._json(404, {"error": f"No sample called {name!r}."})
            return self._json(200, normalize(SAMPLES[name]))
        if path == "/":
            path = "/index.html"
        target = (STATIC / path.lstrip("/")).resolve()
        if STATIC not in target.parents or not target.is_file():
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/respond":
            return self._json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > MAX_BODY:
                return self._json(413, {"error": "Message too long."})
            payload = json.loads(self.rfile.read(length) or b"{}")
            messages = payload.get("messages")
            if not isinstance(messages, list) or not messages:
                return self._json(400, {"error": "No messages sent."})
            messages = [{"role": str(m.get("role")), "content": str(m.get("content", ""))} for m in messages]
            return self._json(200, normalize(respond(messages)))
        except Exception as e:  # keep the demo alive on rate limits etc.
            traceback.print_exc()
            return self._json(502, {"error": f"The planner hit a problem: {e}"})

    def log_message(self, fmt: str, *args) -> None:
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("%s\n" % (fmt % args))


def main() -> None:
    port = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Relo AI running at http://localhost:{port}  ({'mock agent' if USE_MOCK else 'agent.py'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
