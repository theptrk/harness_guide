"""Level 1 — hold a conversation.

    uv run --env-file .env levels/01-conversation/main.py          # continue
    uv run --env-file .env levels/01-conversation/main.py --new    # start fresh
"""

import os
import sys

from openai import OpenAI

import history

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."


def last_message_phase(response) -> str | None:
    """Phase on the last message item. The API wants this sent back next turn."""
    phase = None
    for item in response.output:
        if item.type == "message":
            phase = item.phase
    return phase


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    client = OpenAI()

    if "--new" in sys.argv:
        chat_file_path = history.new_chat()
    else:
        chat_file_path = history.latest_chat() or history.new_chat()

    messages = history.get_messages(chat_file_path)
    print(f"[{chat_file_path.name} · {len(messages)} messages so far]")
    print("Ctrl-D to leave. Nothing is lost when you do.\n")

    while True:
        try:
            said = input("you › ").strip()
        except EOFError:
            print()
            break
        if not said:
            continue

        # Write it down first, then read the file back. Never keep the list in
        # a variable across turns — the file is the record, the list is derived.
        history.append(chat_file_path, "user", said)
        messages = history.get_messages(chat_file_path)

        try:
            response = client.responses.create(
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=messages,
                reasoning={"effort": "none"},
            )
        except KeyboardInterrupt:
            history.drop_last(chat_file_path)
            print()
            break
        except Exception as e:
            history.drop_last(chat_file_path)
            print(f"call failed: {e}", file=sys.stderr)
            continue

        answer = response.output_text
        history.append(
            chat_file_path,
            "assistant",
            answer,
            phase=last_message_phase(response),
        )

        used = response.usage
        reasoning = used.output_tokens_details.reasoning_tokens
        print(f"\n››› {answer}")
        print(f"    [{used.input_tokens} in + {used.output_tokens} out  {reasoning} reasoning]\n")


if __name__ == "__main__":
    main()
