"""Level 3 — keep calling tools until the model answers.

    uv run --env-file .env levels/03-loop/main.py
    uv run --env-file .env levels/03-loop/main.py --new
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI

import history

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."

TOOLS = [
    {
        "type": "function",
        "name": "get_current_time",
        "description": "Get the current date and time in a specific timezone.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "An IANA timezone name, such as Asia/Tokyo or America/New_York.",
                }
            },
            "required": ["timezone"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]


def get_current_time(timezone: str) -> str:
    """Return the current time in an IANA timezone as JSON."""
    now = datetime.now(ZoneInfo(timezone))
    return json.dumps(
        {
            "timezone": timezone,
            "datetime": now.isoformat(timespec="seconds"),
        }
    )


TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
}


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    client = OpenAI()

    if "--new" in sys.argv:
        chat_file_path = history.new_chat()
    else:
        chat_file_path = history.latest_chat() or history.new_chat()

    input_items = history.get_input_items(chat_file_path)
    print(f"[{chat_file_path.name} · {len(input_items)} items so far]")
    print("Ctrl-D to leave. Every API item is saved.\n")

    while True:
        try:
            said = input("you › ").strip()
        except EOFError:
            print()
            break
        if not said:
            continue

        history.append_item(
            chat_file_path,
            {"role": "user", "content": said},
        )
        only_user_item_written = True
        model_calls = 0
        input_tokens = 0
        output_tokens = 0

        try:
            while True:
                input_items = history.get_input_items(chat_file_path)
                response = client.responses.create(
                    model=MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=input_items,
                    tools=TOOLS,
                    parallel_tool_calls=False,
                    reasoning={"effort": "none"},
                )
                for output_item in response.output:
                    history.append_item(
                        chat_file_path,
                        output_item.model_dump(mode="json", exclude_none=True),
                    )
                only_user_item_written = False
                model_calls += 1
                input_tokens += response.usage.input_tokens
                output_tokens += response.usage.output_tokens

                tool_call = next(
                    (item for item in response.output if item.type == "function_call"),
                    None,
                )
                if tool_call is None:
                    answer = response.output_text
                    break

                print(f"\ntool › {tool_call.name}({tool_call.arguments})")
                arguments = json.loads(tool_call.arguments)
                tool_function = TOOL_FUNCTIONS.get(tool_call.name)
                if tool_function is None:
                    raise RuntimeError(f"unknown tool: {tool_call.name}")
                tool_result = tool_function(**arguments)
                print(f"tool ‹ {tool_result}")

                history.append_item(
                    chat_file_path,
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": tool_result,
                    },
                )
        except KeyboardInterrupt:
            if only_user_item_written:
                history.drop_last_item(chat_file_path)
            print()
            break
        except Exception as error:
            if only_user_item_written:
                history.drop_last_item(chat_file_path)
            print(f"call failed: {error}", file=sys.stderr)
            continue

        if not answer:
            print("\n[stopped: model returned no answer]")
            print(f"    [{model_calls} model call(s) · {input_tokens} in + {output_tokens} out]\n")
            continue

        print(f"\n››› {answer}")
        print(f"    [{model_calls} model call(s) · {input_tokens} in + {output_tokens} out]\n")


if __name__ == "__main__":
    main()
