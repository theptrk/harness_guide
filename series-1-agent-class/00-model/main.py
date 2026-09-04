"""Level 0 — call a model.

    uv run --env-file .env series-1-agent-class/00-model/main.py "why is the sky blue"
    uv run --env-file .env series-1-agent-class/00-model/main.py --raw "why is the sky blue"

--raw prints the whole response object before the answer. Reference for what
you're looking at:
https://developers.openai.com/api/reference/python/resources/responses/methods/create
"""

import os
import sys
from collections.abc import Callable

from openai import OpenAI

MODEL = "gpt-5.6-luna"

SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."

Emit = Callable[[dict], None]


class Agent:
    """One model client that can handle a message.

    The agent never prints. It reports what happened by calling emit with a
    dict whose "type" is one of: response, text, done.
    """

    def __init__(self, client: OpenAI, *, emit: Emit):
        self.client = client
        self.emit = emit

    def handle_message(self, question: str) -> None:
        """Send one question and report the response."""
        response = self.client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,  # applies to every question
            input=question,              # this question
            reasoning={"effort": "none"},
        )

        # The whole response object, as the SDK parsed it.
        self.emit({"type": "response", "response": response})
        # The answer, read out of it.
        self.emit({"type": "text", "text": response.output_text})
        used = response.usage
        self.emit(
            {
                "type": "done",
                "input_tokens": used.input_tokens,
                "output_tokens": used.output_tokens,
                "reasoning_tokens": used.output_tokens_details.reasoning_tokens,
                "status": response.status,
                "model": response.model,
            }
        )


class Terminal:
    """Print agent events."""

    def __init__(self, raw: bool):
        self.raw = raw

    def emit(self, event: dict) -> None:
        kind = event["type"]
        if kind == "response":
            # What actually came back over the wire. Everything below is read out of this.
            if self.raw:
                print(event["response"].model_dump_json(indent=2))
                print("\n" + "─" * 60 + "\n", file=sys.stderr)
        elif kind == "text":
            print(f"🤖 model › {event['text']}")
        elif kind == "done":
            print(
                f"\n[{event['input_tokens']} input + {event['output_tokens']} output tokens"
                f"  {event['reasoning_tokens']} reasoning tokens"
                f"  status={event['status']}]",
                file=sys.stderr,
            )
            if event["model"] != MODEL:
                print(
                    f"  note: asked for {MODEL}, served by {event['model']}.",
                    file=sys.stderr,
                )


def main() -> None:
    args = sys.argv[1:]
    raw = "--raw" in args
    question = " ".join(a for a in args if a != "--raw")
    if not question:
        sys.exit('usage: main.py [--raw] "your question"')
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    # OpenAI() reads OPENAI_API_KEY from the environment. The key is never in this file.
    terminal = Terminal(raw=raw)
    agent = Agent(OpenAI(), emit=terminal.emit)
    agent.handle_message(question)


if __name__ == "__main__":
    main()
