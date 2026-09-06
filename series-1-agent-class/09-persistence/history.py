"""Append-only JSONL store of completed conversation turns.

Each line wraps one Responses API item with a local timestamp.
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


def append_items(path: Path, items: list[dict]) -> None:
    """Append one completed turn of API items."""
    lines = [
        json.dumps({"at": datetime.now().isoformat(), "item": item}) + "\n"
        for item in items
    ]
    with path.open("a") as file:
        file.writelines(lines)


def get_input_items(path: Path) -> list[dict]:
    """Return every stored item as Responses API input."""
    items = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        items.append(json.loads(line)["item"])
    return items
