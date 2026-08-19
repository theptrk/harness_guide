"""The record of what was said.

One file per conversation under chats/. One line per message, appended as it
happens. Lines are not rewritten. The one deletion is an unsent user line when
the call fails, so a retry isn't a second copy of a question that never landed.

The list of messages you send to the model is *built from* this file. It is not
the file. That distinction does nothing for you today and is the whole reason
Level 10 is possible.
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
    """Build the list to send to the model, out of the file.

    Right now this is every line in order. At Level 10 it stops being that:
    it starts from the newest summary and reads forward. The callers won't
    change — only this function will.

    `at` stays on disk and is not sent. `phase` is sent when present — the
    API asks that follow-up calls include it on assistant messages.
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
