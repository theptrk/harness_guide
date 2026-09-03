"""HTTP front end for the local agent.

    uv run --env-file .env web/server.py
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
STATIC_DIR = ROOT / "static"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent

HOST = "127.0.0.1"
PORT = 8765

turn_lock = threading.Lock()
approval = {
    "event": threading.Event(),
    "approved": False,
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ApprovalRequest(BaseModel):
    approved: bool


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    agent.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def emit_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/api/chat")
def get_chat() -> dict:
    return agent.snapshot()


@app.post("/api/chat/new")
def new_chat() -> dict:
    agent.new_chat()
    return {"ok": True}


@app.post("/api/approve")
def approve_command(request: ApprovalRequest) -> dict:
    approval["approved"] = request.approved
    approval["event"].set()
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
    if not turn_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a turn is already running")

    events: queue.Queue[dict | None] = queue.Queue()

    def emit(payload: dict) -> None:
        events.put(payload)

    def approve(command: str) -> bool:
        approval["approved"] = False
        approval["event"].clear()
        emit({"type": "approval", "command": command})
        if not approval["event"].wait(timeout=600):
            return False
        return approval["approved"]

    def run_turn() -> None:
        try:
            agent.handle_message(message, emit=emit, approve=approve)
        except Exception as error:
            emit({"type": "error", "message": str(error)})
        finally:
            events.put(None)
            turn_lock.release()

    threading.Thread(target=run_turn, daemon=True).start()

    async def stream() -> AsyncIterator[str]:
        try:
            while True:
                payload = await asyncio.to_thread(events.get)
                if payload is None:
                    break
                yield emit_sse(payload)
        finally:
            approval["event"].set()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")
    print(f"Open http://{HOST}:{PORT}")
    print(f"[workspace: {agent.workspace_label()}]")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
