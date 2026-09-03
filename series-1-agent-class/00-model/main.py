"""Level 0 — call a model.

    uv run --env-file .env series-1-agent-class/00-model/main.py "why is the sky blue"
    uv run --env-file .env series-1-agent-class/00-model/main.py --raw "why is the sky blue"

--raw prints the whole response object before the answer. Reference for what
you're looking at:
https://developers.openai.com/api/reference/python/resources/responses/methods/create
"""

import os
import sys

from openai import OpenAI

MODEL = "gpt-5.6-luna"

SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."


class Agent:
    """One model client that can handle a message."""

    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

        # Reads OPENAI_API_KEY from the environment. The key is never in this file.
        self.client = OpenAI()

    def handle_message(self, question: str, raw: bool = False) -> None:
        """Send one question and print the response."""
        response = self.client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,  # applies to every question
            input=question,              # this question
            reasoning={"effort": "none"},
        )

        # What actually came back over the wire. Everything below is read out of this.
        if raw:
            print(response.model_dump_json(indent=2))
            print("\n" + "─" * 60 + "\n", file=sys.stderr)

        print(f"🤖 model › {response.output_text}")

        used = response.usage
        reasoning = used.output_tokens_details.reasoning_tokens
        print(
            f"\n[{used.input_tokens} input + {used.output_tokens} output tokens"
            f"  {reasoning} reasoning tokens"
            f"  status={response.status}]",
            file=sys.stderr,
        )

        if response.model != MODEL:
            print(
                f"  note: asked for {MODEL}, served by {response.model}.",
                file=sys.stderr,
            )


def main() -> None:
    args = sys.argv[1:]
    raw = "--raw" in args
    question = " ".join(a for a in args if a != "--raw")
    if not question:
        sys.exit('usage: main.py [--raw] "your question"')

    agent = Agent()
    agent.handle_message(question, raw)

if __name__ == "__main__":
    main()
