"""Level 1 — hold a conversation.

    uv run --env-file .env series-1-agent-class/01-conversation/main.py
    uv run --env-file .env series-1-agent-class/01-conversation/main.py --raw
    uv run --env-file .env series-1-agent-class/01-conversation/main.py --raw_model_dump
"""

import json
import os
import sys

from openai import OpenAI

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."


class Agent:
    """One model client and one conversation."""

    def __init__(self, raw: bool = False, raw_model_dump: bool = False):
        if not os.getenv("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

        self.client = OpenAI()
        self.input_items = []
        self.raw = raw
        self.raw_model_dump = raw_model_dump
        print("Ctrl-D to leave.\n")

    def handle_message(self, said: str) -> None:
        """Send one user message and retain the completed exchange."""
        user_item = {"role": "user", "content": said}

        try:
            response = self.client.responses.create(
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=self.input_items + [user_item],
                reasoning={"effort": "none"},
            )
        except KeyboardInterrupt:
            print()
            raise SystemExit
        except Exception as e:
            print(f"call failed: {e}", file=sys.stderr)
            return

        output_items = [
            item.model_dump(mode="json", exclude_none=True)
            for item in response.output
        ]

        if self.raw:
            print(json.dumps(output_items, indent=2))
            print("\n" + "─" * 60 + "\n", file=sys.stderr)

        if self.raw_model_dump:
            print(response.model_dump_json(indent=2))
            print("\n" + "─" * 60 + "\n", file=sys.stderr)

        self.input_items.append(user_item)
        self.input_items.extend(output_items)

        used = response.usage
        reasoning = used.output_tokens_details.reasoning_tokens
        print(f"\n🤖 model › {response.output_text}")
        print(f"    [{used.input_tokens} in + {used.output_tokens} out  {reasoning} reasoning]\n")


def main() -> None:
    raw = "--raw" in sys.argv[1:]
    raw_model_dump = "--raw_model_dump" in sys.argv[1:]
    agent = Agent(raw=raw, raw_model_dump=raw_model_dump)

    while True:
        try:
            said = input("📝 you › ").strip()
        except EOFError:
            print()
            break
        if said:
            agent.handle_message(said)


if __name__ == "__main__":
    main()
