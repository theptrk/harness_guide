"""Append-only JSONL store of Responses API items.

Each line wraps one API item with a local timestamp. The API never sees the
wrapper. `get_input_items()` returns the `input` list.
"""

import json
from datetime import datetime
from pathlib import Path

CHATS = Path(__file__).parent / "chats"


def new_chat() -> Path:
    """Create an empty conversation file."""
    CHATS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
    path = CHATS / f"{stamp}.jsonl"
    path.touch(exist_ok=False)
    return path


def latest_chat() -> Path | None:
    """Return the most recently started conversation."""
    if not CHATS.exists():
        return None
    chats = sorted(CHATS.glob("*.jsonl"))
    return chats[-1] if chats else None


def append_item(path: Path, item: dict) -> None:
    """Append one API input or output item with a local timestamp."""
    line = {"at": datetime.now().isoformat(), "item": item}
    with path.open("a") as file:
        file.write(json.dumps(line) + "\n")


def drop_last_item(path: Path) -> None:
    """Remove the item most recently appended."""
    text = path.read_text()
    if not text:
        return
    lines = text.splitlines(keepends=True)
    path.write_text("".join(lines[:-1]))


def get_input_items(path: Path) -> list[dict]:
    """Return the Responses API `input` list stored in this file.

    Each JSONL line is local (`at` plus an `item`). The return value is only
    the items. That list is what `responses.create(input=...)` accepts.

    The fallback reads message-only files made by the first version of Level 2.
    """
    items = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if "item" in entry:
            items.append(entry["item"])
            continue

        message = {"role": entry["role"], "content": entry["content"]}
        if entry.get("phase"):
            message["phase"] = entry["phase"]
        items.append(message)
    return without_unanswered_calls(items)


def without_unanswered_calls(items: list[dict]) -> list[dict]:
    """Drop function calls that have no matching output.

    Writing happens one item at a time, so killing the process between a
    `function_call` and its `function_call_output` leaves a call unanswered on
    disk. The API rejects input containing one, which would make the file
    unusable for the rest of the conversation. Leaving the call out is a read
    of a truncated record, not a repair of the file.
    """
    answered = {
        item["call_id"] for item in items if item.get("type") == "function_call_output"
    }
    return [
        item
        for item in items
        if item.get("type") != "function_call" or item["call_id"] in answered
    ]
