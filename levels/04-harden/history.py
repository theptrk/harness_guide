"""Persist complete and incomplete API items as typed JSONL events."""

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


def append_event(path: Path, kind: str, **data) -> None:
    """Append one typed event with a local timestamp."""
    event = {
        "at": datetime.now().isoformat(),
        "kind": kind,
        **data,
    }
    with path.open("a") as file:
        file.write(json.dumps(event) + "\n")


def append_api_item(path: Path, item: dict) -> None:
    """Append an item eligible for later model input."""
    append_event(path, "api_item", item=item)


def append_incomplete_item(path: Path, item: dict) -> None:
    """Append incomplete output that must never become model input."""
    append_event(path, "incomplete_item", item=item)


def drop_last_item(path: Path) -> None:
    """Remove the item most recently appended."""
    text = path.read_text()
    if not text:
        return
    lines = text.splitlines(keepends=True)
    path.write_text("".join(lines[:-1]))


def get_input_items(path: Path) -> list[dict]:
    """Project API item events into model input."""
    items = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry["kind"] == "api_item":
            items.append(entry["item"])
    return items
