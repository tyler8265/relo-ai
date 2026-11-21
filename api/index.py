"""Vercel entry point: the same JSON API as frontend/server.py, as a FastAPI app.

Vercel sends every request here: /api/* is handled below, and everything else is served
from frontend/static/ (index.html, app.js, styles, fonts).
Run locally with:  uvicorn api.index:app --port 8002   (from the repo root)
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "frontend", ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import backend_bridge  # noqa: E402  (frontend/backend_bridge.py)
from adapter import normalize  # noqa: E402  (frontend/adapter.py)
from sample_data import SAMPLES  # noqa: E402  (frontend/sample_data.py)

MAX_BODY = 200_000

app = FastAPI()


@app.get("/api/config")
def config() -> dict:
    st = backend_bridge.status()
    return {"mock": not st["live"] and not st["backend"], **st}


@app.get("/api/sample")
def sample(name: str = "options"):
    if name not in SAMPLES:
        return JSONResponse({"error": f"No sample called {name!r}."}, status_code=404)
    return normalize(SAMPLES[name])


@app.post("/api/respond")
async def respond(request: Request):
    body = await request.body()
    if len(body) > MAX_BODY:
        return JSONResponse({"error": "Message too long."}, status_code=413)
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"error": "No messages sent."}, status_code=400)
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list) or not messages:
        return JSONResponse({"error": "No messages sent."}, status_code=400)
    messages = [{"role": str(m.get("role")), "content": str(m.get("content", ""))}
                for m in messages if isinstance(m, dict)]
    try:
        raw, source = backend_bridge.respond(messages)
        return {**normalize(raw), "source": source}
    except Exception as e:  # keep the demo alive on rate limits etc.
        traceback.print_exc()
        return JSONResponse({"error": f"The planner hit a problem: {e}"}, status_code=502)


# Last, so the /api routes above take priority. html=True serves index.html at "/".
app.mount("/", StaticFiles(directory=ROOT / "frontend" / "static", html=True), name="static")
