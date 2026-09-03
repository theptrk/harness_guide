"""HTTP front end for one local agent.

    uv run --env-file .env web-single-agent/server.py
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import sys
import threading
from collections.abc import AsyncIterator
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent

HOST = "127.0.0.1"
PORT = 8765
SSE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Accel-Buffering": "no",
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


app = FastAPI()
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def blocking_mode() -> bool:
    """Report whether BLOCK_EVENT_LOOP=1 asked for the lesson 1 route."""
    return os.getenv("BLOCK_EVENT_LOOP") == "1"


def sse_frame(payload: dict) -> str:
    """Format one agent event as a Server-Sent Events frame."""
    return f"data: {json.dumps(payload)}\n\n"


async def collected_turn(message: str) -> AsyncIterator[str]:
    """Run the turn on the event-loop thread, then send every event at once.

    This is the lesson 1 route. It holds the event loop for the whole turn, so
    no other request is served until the model answers. Run
    demos/held_event_loop.py to measure that.
    """
    events: list[dict] = []
    try:
        agent.handle_message(message, emit=events.append)
    except Exception as error:
        events.append({"type": "error", "message": str(error)})
    for payload in events:
        yield sse_frame(payload)


async def streamed_turn(message: str) -> AsyncIterator[str]:
    """Run the turn on a worker thread and forward events as they arrive.

    The worker thread puts events on a queue. This coroutine takes them off
    with asyncio.to_thread, so waiting for the next event never holds the event
    loop.
    """
    events: queue.Queue[dict | None] = queue.Queue()

    def run() -> None:
        try:
            agent.handle_message(message, emit=events.put)
        except Exception as error:
            events.put({"type": "error", "message": str(error)})
        finally:
            events.put(None)

    threading.Thread(target=run, name="agent-turn", daemon=True).start()

    while True:
        payload = await asyncio.to_thread(events.get)
        if payload is None:
            break
        yield sse_frame(payload)


@app.get("/api/ping")
def get_ping() -> dict:
    """Answer immediately. demos/held_event_loop.py times this route."""
    return {"ok": True}


@app.get("/api/chat")
def get_chat() -> dict:
    return agent.snapshot()


@app.post("/api/chat/new")
def post_new_chat() -> dict:
    agent.new_chat()
    return {"ok": True}


@app.post("/api/chat")
async def post_chat(request: ChatRequest) -> StreamingResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not set. Copy .env.example to .env.",
        )
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    frames = collected_turn(message) if blocking_mode() else streamed_turn(message)
    return StreamingResponse(frames, media_type="text/event-stream", headers=SSE_HEADERS)


@app.get("/")
def get_index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")
    print(f"Open http://{HOST}:{PORT}")
    print(f"[workspace: {agent.workspace_label()}]")
    if blocking_mode():
        print("[BLOCK_EVENT_LOOP=1: the turn runs on the event-loop thread]")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
