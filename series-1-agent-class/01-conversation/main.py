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

    def __init__(self, client: OpenAI):
        self.client = client
        self.input_items = []

    def handle_message(self, said: str):
        """Send one user message, retain the completed exchange, return the response."""
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
        return response


def main() -> None:
    raw = "--raw" in sys.argv[1:]
    raw_model_dump = "--raw_model_dump" in sys.argv[1:]
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    agent = Agent(OpenAI())
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
            response = agent.handle_message(said)
        except KeyboardInterrupt:
            print()
            break
        except Exception as error:
            print(f"call failed: {error}", file=sys.stderr)
            continue

        if raw:
            output_items = [
                item.model_dump(mode="json", exclude_none=True)
                for item in response.output
            ]
            print(json.dumps(output_items, indent=2))
            print("\n" + "─" * 60 + "\n", file=sys.stderr)

        if raw_model_dump:
            print(response.model_dump_json(indent=2))
            print("\n" + "─" * 60 + "\n", file=sys.stderr)

        used = response.usage
        reasoning = used.output_tokens_details.reasoning_tokens
        print(f"\n🤖 model › {response.output_text}")
        print(f"    [{used.input_tokens} in + {used.output_tokens} out  {reasoning} reasoning]\n")


if __name__ == "__main__":
    main()
