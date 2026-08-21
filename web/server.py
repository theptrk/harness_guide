"""ChatGPT-style local chat UI for the harness.

    uv run --env-file .env web/server.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from openai import OpenAI, OpenAIError

ROOT = Path(__file__).parent
CHATS = ROOT / "chats"
MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."
HOST = "127.0.0.1"
PORT = 8765
STATIC_FILES = {
    "/": ROOT / "index.html",
    "/index.html": ROOT / "index.html",
    "/styles.css": ROOT / "styles.css",
    "/app.js": ROOT / "app.js",
}

client = OpenAI()


def latest_chat() -> Path | None:
    if not CHATS.exists():
        return None
    chats = sorted(CHATS.glob("*.jsonl"))
    return chats[-1] if chats else None


def new_chat() -> Path:
    CHATS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    path = CHATS / f"{stamp}.jsonl"
    path.touch(exist_ok=False)
    return path


def current_chat() -> Path:
    return latest_chat() or new_chat()


def read_messages(path: Path) -> list[dict]:
    messages = []
    if not path.exists() or path.stat().st_size == 0:
        return messages
    for line in path.read_text().splitlines():
        if line.strip():
            messages.append(json.loads(line))
    return messages


def append_message(path: Path, role: str, text: str) -> dict:
    message = {
        "role": role,
        "text": text,
        "at": datetime.now().isoformat(),
    }
    with path.open("a") as file:
        file.write(json.dumps(message) + "\n")
    return message


def conversation_title(messages: list[dict]) -> str:
    for message in messages:
        if message.get("role") == "user" and message.get("text", "").strip():
            text = " ".join(message["text"].split())
            return text if len(text) <= 48 else f"{text[:45]}..."
    return "New chat"


def input_items(messages: list[dict]) -> list[dict]:
    return [{"role": message["role"], "content": message["text"]} for message in messages]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode() or "{}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/chat":
            messages = read_messages(current_chat())
            payload = json.dumps(
                {
                    "title": conversation_title(messages),
                    "messages": messages,
                }
            ).encode()
            self._send(200, payload, "application/json; charset=utf-8")
            return

        static_path = STATIC_FILES.get(path)
        if static_path is None or not static_path.exists():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }[static_path.suffix]
        self._send(200, static_path.read_bytes(), content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/chat/new":
            new_chat()
            self._send(200, b'{"ok":true}', "application/json; charset=utf-8")
            return
        if path != "/api/chat":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        if not os.getenv("OPENAI_API_KEY"):
            self._send(
                500,
                b"OPENAI_API_KEY is not set. Copy .env.example to .env.",
                "text/plain; charset=utf-8",
            )
            return

        request = self._read_json()
        text = str(request.get("message", "")).strip()
        if not text:
            self._send(400, b"message is required", "text/plain; charset=utf-8")
            return

        chat_path = current_chat()
        messages = read_messages(chat_path)
        if request.get("regenerate") and messages and messages[-1]["role"] == "assistant":
            messages = messages[:-1]
            chat_path.write_text("".join(json.dumps(message) + "\n" for message in messages))
        if not request.get("regenerate"):
            append_message(chat_path, "user", text)
            messages = read_messages(chat_path)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        def emit(payload: dict) -> None:
            self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
            self.wfile.flush()

        emit({"type": "title", "title": conversation_title(messages)})
        answer = []
        try:
            with client.responses.create(
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=input_items(messages),
                reasoning={"effort": "none"},
                stream=True,
            ) as stream:
                for event in stream:
                    if event.type in {
                        "response.output_text.delta",
                        "response.refusal.delta",
                    }:
                        answer.append(event.delta)
                        emit({"type": "delta", "text": event.delta})
        except OpenAIError as error:
            emit({"type": "error", "message": str(error)})
            return
        except BrokenPipeError:
            return

        if answer:
            append_message(chat_path, "assistant", "".join(answer))
        emit({"type": "done"})


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Open http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        server.server_close()


if __name__ == "__main__":
    main()
