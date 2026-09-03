"""Level 7 — use one persistent browser page.

    uv run --env-file .env series-1-agent-class/07-browser/main.py
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI

import browser_tools
import file_tools
import shell_tools

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = (
    "You are a concise coding assistant. Use the tools to inspect and modify files, "
    "run commands, and operate one persistent browser page. Every shell command "
    "requires approval. A denied command is a final decision: do not request the "
    "same denied action again unless the person explicitly asks. If a page requires "
    "a CAPTCHA or other human verification, ask the person to complete it in the "
    "visible browser and tell you when they are done. Do not claim an action "
    "succeeded unless its tool result says it did."
)
TOOL_CALL_LIMIT = 5

TIME_TOOL = {
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

TOOLS = (
    [TIME_TOOL]
    + file_tools.TOOLS
    + [shell_tools.RUN_COMMAND_TOOL]
    + browser_tools.TOOLS
)


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
    "list_files": file_tools.list_files,
    "read_file": file_tools.read_file,
    "write_file": file_tools.write_file,
    "edit_file": file_tools.edit_file,
    "run_command": shell_tools.run_command,
    "open_page": browser_tools.open_page,
    "read_page": browser_tools.read_page,
    "type_text": browser_tools.type_text,
    "click": browser_tools.click,
}


class Agent:
    """One model client and one conversation."""

    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

        self.client = OpenAI()
        self.input_items = []
        print("[workspace: series-1-agent-class/07-browser/agent_workspace]")
        print("Ctrl-D to leave. Ctrl-C interrupts the active turn.\n")

    @staticmethod
    def _display_tool_result(tool_result: str) -> str:
        """Format JSON for the terminal without changing the stored tool result."""
        try:
            value = json.loads(tool_result)
        except json.JSONDecodeError:
            return tool_result
        return json.dumps(value, indent=2)

    def _run_tool(self, tool_call) -> str:
        """Run one requested tool, converting any failure into tool output."""
        try:
            arguments = json.loads(tool_call.arguments)
            tool_function = TOOL_FUNCTIONS.get(tool_call.name)
            if tool_function is None:
                raise LookupError(f"unknown tool: {tool_call.name}")
            return tool_function(**arguments)
        except Exception as error:
            return f"{type(error).__name__}: {error}"

    def _stream_response(
        self,
        model_call: int,
        input_items: list[dict],
        force_answer: bool,
    ):
        """Print text deltas, then return the terminal response."""
        print(f"\n[model call {model_call} started]", flush=True)

        final_response = None
        text_started = False
        with self.client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=input_items,
            tools=TOOLS,
            tool_choice="none" if force_answer else "auto",
            parallel_tool_calls=False,
            reasoning={"effort": "none"},
            stream=True,
        ) as stream:
            for event in stream:
                if event.type in {
                    "response.output_text.delta",
                    "response.refusal.delta",
                }:
                    if not text_started:
                        print("\n🤖 model › ", end="", flush=True)
                    print(event.delta, end="", flush=True)
                    text_started = True
                elif event.type == "response.completed":
                    final_response = event.response

        if text_started:
            print()
        if final_response is None:
            raise RuntimeError("model stream ended without a terminal response")
        return final_response, text_started

    def handle_message(self, said: str) -> None:
        """Run one user request until the model returns an answer."""
        turn_items = [{"role": "user", "content": said}]
        model_calls = 0
        tool_calls = 0
        input_tokens = 0
        output_tokens = 0
        force_answer = False

        try:
            while True:
                response, text_was_streamed = self._stream_response(
                    model_calls + 1,
                    self.input_items + turn_items,
                    force_answer,
                )
                model_calls += 1
                if response.usage is not None:
                    input_tokens += response.usage.input_tokens
                    output_tokens += response.usage.output_tokens
                turn_items.extend(
                    item.model_dump(mode="json", exclude_none=True)
                    for item in response.output
                )

                # response.output may contain messages, function calls, or other
                # item types. Find the function call relevant to this lesson.
                tool_call = next(
                    (item for item in response.output if item.type == "function_call"),
                    None,
                )

                if tool_call is None:
                    # No tool request means the model has finished this turn.
                    if not text_was_streamed:
                        print(f"\n🤖 model › {response.output_text}")
                    break
                if force_answer:
                    raise RuntimeError("model requested a tool after tool use was disabled")

                print(f"\ntool › {tool_call.name}({tool_call.arguments})")
                if tool_calls >= TOOL_CALL_LIMIT:
                    tool_result = (
                        f"ToolCallLimit: the limit of {TOOL_CALL_LIMIT} "
                        "tool calls has been reached"
                    )
                    force_answer = True
                else:
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
        except KeyboardInterrupt:
            print("\n[turn interrupted]")
            raise
        except Exception as e:
            print(f"call failed: {e}", file=sys.stderr)
            return

        self.input_items.extend(turn_items)
        print(
            f"    [{model_calls} model call(s) · {tool_calls} tool call(s) · "
            f"{input_tokens} in + {output_tokens} out]\n"
        )


def main() -> None:
    agent = Agent()

    try:
        while True:
            try:
                said = input("📝 you › ").strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                break
            if said:
                try:
                    agent.handle_message(said)
                except KeyboardInterrupt:
                    break
    finally:
        browser_tools.close_browser()


if __name__ == "__main__":
    main()
