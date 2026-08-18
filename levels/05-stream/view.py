"""Replay a Level 5 event log, optionally following new events.

    uv run levels/05-stream/view.py levels/05-stream/chats/<chat>.jsonl
    uv run levels/05-stream/view.py --follow levels/05-stream/chats/<chat>.jsonl
"""

import json
import sys
import time
from pathlib import Path


class Renderer:
    """Project stored events into terminal output."""

    def __init__(self) -> None:
        self.text_open = False

    def close_text(self) -> None:
        if self.text_open:
            print()
            self.text_open = False

    def render(self, event: dict) -> None:
        kind = event["kind"]

        if kind == "api_item":
            item = event["item"]
            if item.get("role") == "user":
                self.close_text()
                print(f"\nyou › {item['content']}")
            elif item.get("type") == "function_call":
                self.close_text()
                print(f"\ntool › {item['name']}({item['arguments']})")
            elif item.get("type") == "function_call_output":
                self.close_text()
                print(f"tool ‹ {item['output']}")
            return

        if kind == "model_started":
            self.close_text()
            print(f"\n[model call {event['model_call']} started]")
        elif kind == "text_delta":
            if event["start"]:
                self.close_text()
                print("\nmodel › ", end="")
                self.text_open = True
            print(event["delta"], end="", flush=True)
        elif kind == "turn_completed":
            self.close_text()
            print(
                f"    [{event['model_calls']} model call(s)"
                f" · {event['tool_calls']} tool call(s)"
                f" · {event['input_tokens']} in + {event['output_tokens']} out]"
            )
        elif kind == "turn_interrupted":
            self.close_text()
            print("\n[turn interrupted]")
        elif kind == "turn_failed":
            self.close_text()
            print(f"\n[turn failed: {event['error_type']}: {event['message']}]")


def arguments() -> tuple[Path, bool]:
    follow = "--follow" in sys.argv
    paths = [Path(argument) for argument in sys.argv[1:] if argument != "--follow"]
    if len(paths) != 1:
        sys.exit("usage: view.py [--follow] CHAT_FILE")
    return paths[0], follow


def main() -> None:
    path, follow = arguments()
    if not path.exists():
        sys.exit(f"chat file does not exist: {path}")

    renderer = Renderer()
    with path.open() as file:
        while True:
            line = file.readline()
            if line:
                renderer.render(json.loads(line))
                continue
            if not follow:
                break
            time.sleep(0.05)
    renderer.close_text()


if __name__ == "__main__":
    main()
