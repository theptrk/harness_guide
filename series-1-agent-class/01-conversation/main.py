"""Level 1 — hold a conversation.

    uv run --env-file .env series-1-agent-class/01-conversation/main.py
"""

import os
import sys

from openai import OpenAI

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."


class Agent:
    """One model client and one conversation."""

    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

        self.client = OpenAI()
        self.input_items = []
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

        self.input_items.append(user_item)
        self.input_items.extend(
            item.model_dump(mode="json", exclude_none=True)
            for item in response.output
        )

        used = response.usage
        reasoning = used.output_tokens_details.reasoning_tokens
        print(f"\n🤖 model › {response.output_text}")
        print(f"    [{used.input_tokens} in + {used.output_tokens} out  {reasoning} reasoning]\n")


def main() -> None:
    agent = Agent()

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
