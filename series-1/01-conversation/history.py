"""The record of what was said.

One file per conversation under chats/. One line per message, appended as it
happens. Lines are not rewritten. The one deletion is an unsent user line when
the call fails, so a retry isn't a second copy of a question that never landed.

The list you pass to `responses.create(input=...)` is built from this file.
That list is the API. The file is this program. Later, context selection can
send a shorter `input` list while the file still holds every message.
"""

import json
from datetime import datetime
from pathlib import Path

CHATS = Path(__file__).parent / "chats"


def new_chat() -> Path:
    """Start a conversation. Named for when it started, so `ls` sorts right."""
    CHATS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    path = CHATS / f"{stamp}.jsonl"
    path.touch(exist_ok=False)
    return path


def latest_chat() -> Path | None:
    """The most recent conversation, or None if there aren't any yet."""
    if not CHATS.exists():
        return None
    chats = sorted(CHATS.glob("*.jsonl"))
    return chats[-1] if chats else None


def append(path: Path, role: str, content: str, phase: str | None = None) -> None:
    """Add one message to the end. This is the only way anything gets written."""
    line = {"role": role, "content": content, "at": datetime.now().isoformat()}
    if phase:
        line["phase"] = phase
    with path.open("a") as f:
        f.write(json.dumps(line) + "\n")


def drop_last(path: Path) -> None:
    """Remove the last line. Used when a call fails after the user line was written."""
    text = path.read_text()
    if not text:
        return
    lines = text.splitlines(keepends=True)
    path.write_text("".join(lines[:-1]))


def get_messages(path: Path) -> list[dict]:
    """Return the Responses `input` list stored in this file.

    `role`, `content`, and `phase` are API fields. `at` is this program and
    stays on disk. Right now this is every message in order. Context selection
    later starts from the newest summary and reads forward. Callers still pass
    the return value to `input=`.
    """
    out = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        msg = {"role": entry["role"], "content": entry["content"]}
        if entry.get("phase"):
            msg["phase"] = entry["phase"]
        out.append(msg)
    return out
