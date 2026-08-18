"""Persist every Responses API item as an append-only JSONL event."""

import json
from datetime import datetime
from pathlib import Path

CHATS = Path(__file__).parent / "chats"


def new_chat() -> Path:
    """Create an empty conversation file."""
    CHATS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = CHATS / f"{stamp}.jsonl"
    path.touch()
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
    """Build API input from the complete event log."""
    items = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        items.append(json.loads(line)["item"])
    return items
