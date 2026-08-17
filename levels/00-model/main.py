"""Level 0 — call a model.

    uv run --env-file .env levels/00-model/main.py "why is the sky blue"
    uv run --env-file .env levels/00-model/main.py --raw "why is the sky blue"

--raw prints the whole response object before the answer. Reference for what
you're looking at:
https://developers.openai.com/api/reference/python/resources/responses/methods/create
"""

import os
import sys

from openai import OpenAI

MODEL = "gpt-5.6"

# Price per million tokens. Look these up for MODEL and fill them in:
# https://platform.openai.com/docs/pricing
# Left at zero, the cost line below reads $0.000000 — which is the point of the
# exercise. You should know what a call costs before you make thousands of them.
PRICE_IN = 0.0
PRICE_OUT = 0.0

SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."


def main() -> None:
    args = sys.argv[1:]
    raw = "--raw" in args
    question = " ".join(a for a in args if a != "--raw")
    if not question:
        sys.exit('usage: main.py [--raw] "your question"')

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    # Reads OPENAI_API_KEY from the environment. The key is never in this file.
    client = OpenAI()

    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,  # applies to every question
        input=question,              # this question
        reasoning={"effort": "none"},
    )

    # What actually came back over the wire. Everything below is read out of this.
    if raw:
        print(response.model_dump_json(indent=2))
        print("\n" + "─" * 60 + "\n", file=sys.stderr)

    print(response.output_text)

    # Everything below is the part most tutorials skip.
    used = response.usage
    reasoning = used.output_tokens_details.reasoning_tokens
    cost = (used.input_tokens * PRICE_IN + used.output_tokens * PRICE_OUT) / 1_000_000
    print(
        f"\n[{used.input_tokens} in + {used.output_tokens} out tokens"
        f"  {reasoning} reasoning"
        f"  ${cost:.6f}  status={response.status}]",
        file=sys.stderr,
    )

    # You asked for one model. Check which one answered — the prices above are
    # for MODEL, so if these differ, the cost printed is for the wrong thing.
    if response.model != MODEL:
        print(
            f"  note: asked for {MODEL}, served by {response.model}."
            f" Price {response.model}, not {MODEL}.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
