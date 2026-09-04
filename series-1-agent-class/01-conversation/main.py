"""Level 1 — hold a conversation.

    uv run --env-file .env series-1-agent-class/01-conversation/main.py
    uv run --env-file .env series-1-agent-class/01-conversation/main.py --raw
    uv run --env-file .env series-1-agent-class/01-conversation/main.py --raw_model_dump
"""

import json
import os
import sys
from collections.abc import Callable

from openai import OpenAI

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."

Emit = Callable[[dict], None]


class Agent:
    """One model client and one conversation.

    The agent never prints. It reports what happened by calling emit with a
    dict whose "type" is one of: response, text, done.
    """

    def __init__(self, client: OpenAI, *, emit: Emit):
        self.client = client
        self.emit = emit
        self.input_items = []

    def handle_message(self, said: str) -> None:
        """Send one user message, retain the completed exchange, report the response."""
        user_item = {"role": "user", "content": said}

        response = self.client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=self.input_items + [user_item],
            reasoning={"effort": "none"},
        )

        self.input_items.append(user_item)
        self.input_items.extend(
            item.model_dump(mode="json", exclude_none=True)
            for item in response.output
        )

        self.emit({"type": "response", "response": response})
        self.emit({"type": "text", "text": response.output_text})
        used = response.usage
        self.emit(
            {
                "type": "done",
                "input_tokens": used.input_tokens,
                "output_tokens": used.output_tokens,
                "reasoning_tokens": used.output_tokens_details.reasoning_tokens,
            }
        )


class Terminal:
    """Print agent events."""

    def __init__(self, raw: bool, raw_model_dump: bool):
        self.raw = raw
        self.raw_model_dump = raw_model_dump

    def emit(self, event: dict) -> None:
        kind = event["type"]
        if kind == "response":
            response = event["response"]
            if self.raw:
                output_items = [
                    item.model_dump(mode="json", exclude_none=True)
                    for item in response.output
                ]
                print(json.dumps(output_items, indent=2))
                print("\n" + "─" * 60 + "\n", file=sys.stderr)
            if self.raw_model_dump:
                print(response.model_dump_json(indent=2))
                print("\n" + "─" * 60 + "\n", file=sys.stderr)
        elif kind == "text":
            print(f"\n🤖 model › {event['text']}")
        elif kind == "done":
            print(
                f"    [{event['input_tokens']} in + {event['output_tokens']} out"
                f"  {event['reasoning_tokens']} reasoning]\n"
            )


def main() -> None:
    raw = "--raw" in sys.argv[1:]
    raw_model_dump = "--raw_model_dump" in sys.argv[1:]
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    terminal = Terminal(raw=raw, raw_model_dump=raw_model_dump)
    agent = Agent(OpenAI(), emit=terminal.emit)
    print("Ctrl-D to leave.\n")

    while True:
        try:
            said = input("📝 you › ").strip()
        except EOFError:
            print()
            break
        if not said:
            continue

        try:
            agent.handle_message(said)
        except KeyboardInterrupt:
            print()
            break
        except Exception as error:
            print(f"call failed: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
