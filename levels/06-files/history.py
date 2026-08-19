"""Persist API items and turn status events in one append-only JSONL record."""

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


def append_event(path: Path, turn_id: str, kind: str, **data) -> None:
    """Append one event."""
    event = {
        "at": datetime.now().isoformat(),
        "turn_id": turn_id,
        "kind": kind,
        **data,
    }
    with path.open("a") as file:
        file.write(json.dumps(event) + "\n")


def append_api_item(
    path: Path,
    turn_id: str,
    item: dict,
) -> None:
    """Append an item eligible for later model input."""
    append_event(
        path,
        turn_id,
        "api_item",
        item=item,
    )


def append_incomplete_item(path: Path, turn_id: str, item: dict) -> None:
    """Append incomplete output that must never become model input."""
    append_event(
        path,
        turn_id,
        "incomplete_item",
        item=item,
    )


def read_events(path: Path) -> list[dict]:
    """Read every event currently in the record."""
    events = []
    for line in path.read_text().splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def get_input_items(path: Path, active_turn_id: str | None = None) -> list[dict]:
    """Build API input from completed turns and the active turn."""
    events = read_events(path)
    completed_turns = {
        event["turn_id"]
        for event in events
        if event["kind"] == "turn_completed"
    }

    items = []
    for event in events:
        if event["kind"] != "api_item":
            continue
        if event["turn_id"] in completed_turns or event["turn_id"] == active_turn_id:
            items.append(event["item"])
    return items
