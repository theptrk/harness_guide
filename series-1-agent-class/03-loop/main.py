"""Level 3 — keep calling tools until the model answers.

    uv run --env-file .env series-1-agent-class/03-loop/main.py
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI

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


def run_turn(client, input_items: list[dict], said: str) -> None:
    """Run one user request until the model returns an answer."""
    turn_items = [{"role": "user", "content": said}]
    model_calls = 0
    input_tokens = 0
    output_tokens = 0

    try:
        while True:
            response = client.responses.create(
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=input_items + turn_items,
                tools=TOOLS,
                parallel_tool_calls=False,
                reasoning={"effort": "none"},
            )
            turn_items.extend(
                item.model_dump(mode="json", exclude_none=True)
                for item in response.output
            )
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

            turn_items.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": tool_result,
                },
            )
    except KeyboardInterrupt:
        raise
    except Exception as error:
        print(f"call failed: {error}", file=sys.stderr)
        return

    input_items.extend(turn_items)

    if not answer:
        print("\n[stopped: model returned no answer]")
        print(f"    [{model_calls} model call(s) · {input_tokens} in + {output_tokens} out]\n")
        return

    print(f"\n🤖 model › {answer}")
    print(f"    [{model_calls} model call(s) · {input_tokens} in + {output_tokens} out]\n")


class Agent:
    """One model client and one conversation."""

    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

        self.client = OpenAI()
        self.input_items = []
        print("Ctrl-D to leave.\n")

    def handle_message(self, said: str) -> None:
        """Run one user request until the model returns an answer."""
        run_turn(self.client, self.input_items, said)


def main() -> None:
    agent = Agent()

    while True:
        try:
            said = input("📝 you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not said:
            continue

        try:
            agent.handle_message(said)
        except KeyboardInterrupt:
            print()
            break


if __name__ == "__main__":
    main()
