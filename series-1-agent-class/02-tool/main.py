"""Level 2 — give the model one tool.

    uv run --env-file .env series-1-agent-class/02-tool/main.py
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


class Agent:
    """One model client and one conversation."""

    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

        self.client = OpenAI()
        self.input_items = []
        print("Ctrl-D to leave.\n")

    @staticmethod
    def _display_tool_result(tool_result: str) -> str:
        """Format JSON for the terminal without changing the stored tool result."""
        try:
            value = json.loads(tool_result)
        except json.JSONDecodeError:
            return tool_result
        return json.dumps(value, indent=2)

    def _run_tool(self, tool_call) -> str:
        """Execute one function_call item returned by the model."""
        arguments = json.loads(tool_call.arguments)
        tool_function = TOOL_FUNCTIONS.get(tool_call.name)
        if tool_function is None:
            raise RuntimeError(f"unknown tool: {tool_call.name}")
        return tool_function(**arguments)

    def handle_message(self, said: str) -> None:
        """Send one message, allowing one tool call before the answer."""
        turn_items = [{"role": "user", "content": said}]
        answer = None
        model_calls = 0
        tool_calls = 0
        input_tokens = 0
        output_tokens = 0

        try:
            # First model call: either answer directly or request the tool.
            response = self.client.responses.create(
                model=MODEL,
                instructions=SYSTEM_PROMPT,
                input=self.input_items + turn_items,
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

            # response.output may contain messages, function calls, or other
            # item types. Find the function call relevant to this lesson.
            tool_call = next(
                (item for item in response.output if item.type == "function_call"),
                None,
            )

            if tool_call is None:
                answer = response.output_text
            else:
                print(f"\ntool › {tool_call.name}({tool_call.arguments})")
                tool_result = self._run_tool(tool_call)
                tool_calls += 1
                print(f"tool ‹ {self._display_tool_result(tool_result)}")

                turn_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": tool_result,
                    },
                )

                # Second model call: it must answer because this lesson allows
                # only one tool call. Level 3 replaces this limit with a loop.
                response = self.client.responses.create(
                    model=MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=self.input_items + turn_items,
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

                next_tool_call = next(
                    (item for item in response.output if item.type == "function_call"),
                    None,
                )

                if next_tool_call is not None:
                    raise RuntimeError(
                        "this lesson allows one tool call, but the model requested "
                        f"another {next_tool_call.name} call"
                    )
                answer = response.output_text

            if not answer:
                raise RuntimeError("model returned no answer")
        except KeyboardInterrupt:
            print()
            raise SystemExit
        except Exception as e:
            print(f"call failed: {e}", file=sys.stderr)
            return

        self.input_items.extend(turn_items)

        print(f"\n🤖 model › {answer}")
        print(
            f"    [{model_calls} model call(s) · {tool_calls} tool call(s) · "
            f"{input_tokens} in + {output_tokens} out]\n"
        )


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
