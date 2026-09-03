"""Level 8 — persist completed conversations as JSONL.

    uv run --env-file .env series-1-agent-class/08-persistence/main.py
    uv run --env-file .env series-1-agent-class/08-persistence/main.py --new
"""

import json
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI

import browser_tools
import file_tools
import history
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


Emit = Callable[[dict], None]


class Agent:
    """One model client, one persistent conversation, and one browser.

    The agent never prints and never reads the keyboard. It reports each step
    of a turn through emit and asks about shell commands through approve.
    Call close() when done so the browser it owns is closed.
    """

    def __init__(
        self,
        client: OpenAI,
        browser: browser_tools.Browser,
        chat_file_path: Path,
        *,
        emit: Emit,
        approve: shell_tools.ApprovalFunction,
    ):
        self.client = client
        self.browser = browser
        self.chat_file_path = chat_file_path
        self.emit = emit
        self.approve = approve
        # Built per agent: run_command needs this agent's approve, and the
        # browser tools are methods of this agent's browser.
        self.tool_functions = {
            "get_current_time": get_current_time,
            "list_files": file_tools.list_files,
            "read_file": file_tools.read_file,
            "write_file": file_tools.write_file,
            "edit_file": file_tools.edit_file,
            "run_command": self._run_command,
            "open_page": self.browser.open_page,
            "read_page": self.browser.read_page,
            "type_text": self.browser.type_text,
            "click": self.browser.click,
        }

    def close(self) -> None:
        """Release what this agent owns. Safe to call if the browser never started."""
        self.browser.close()

    def _run_command(self, command: str) -> str:
        """Run one shell command after this agent's approve function says yes."""
        return shell_tools.run_command(command, approve=self.approve)

    def _run_tool(self, tool_call) -> str:
        """Run one requested tool, converting any failure into tool output."""
        try:
            arguments = json.loads(tool_call.arguments)
            tool_function = self.tool_functions.get(tool_call.name)
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
        """Emit text fragments as they arrive, then return the terminal response."""
        self.emit({"type": "model_started", "model_call": model_call})

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
                    self.emit({"type": "text", "text": event.delta})
                    text_started = True
                elif event.type == "response.completed":
                    final_response = event.response

        if final_response is None:
            raise RuntimeError("model stream ended without a terminal response")
        return final_response, text_started

    def handle_message(self, said: str) -> None:
        """Run one user request until the model returns an answer."""
        input_items = history.get_input_items(self.chat_file_path)
        turn_items = [{"role": "user", "content": said}]
        model_calls = 0
        tool_calls = 0
        input_tokens = 0
        output_tokens = 0
        force_answer = False

        while True:
            response, text_was_streamed = self._stream_response(
                model_calls + 1,
                input_items + turn_items,
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
                    self.emit({"type": "text", "text": response.output_text})
                break
            if force_answer:
                raise RuntimeError("model requested a tool after tool use was disabled")

            self.emit({"type": "tool", "name": tool_call.name, "arguments": tool_call.arguments})
            if tool_calls >= TOOL_CALL_LIMIT:
                tool_result = (
                    f"ToolCallLimit: the limit of {TOOL_CALL_LIMIT} "
                    "tool calls has been reached"
                )
                force_answer = True
            else:
                tool_result = self._run_tool(tool_call)
                tool_calls += 1
            self.emit({"type": "tool_result", "name": tool_call.name, "output": tool_result})

            turn_items.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": tool_result,
                },
            )

        history.append_items(self.chat_file_path, turn_items)
        self.emit(
            {
                "type": "done",
                "model_calls": model_calls,
                "tool_calls": tool_calls,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )


def display_tool_result(tool_result: str) -> str:
    """Format JSON for the terminal without changing the stored tool result."""
    try:
        value = json.loads(tool_result)
    except json.JSONDecodeError:
        return tool_result
    return json.dumps(value, indent=2)


class Terminal:
    """Print agent events and ask the person at the keyboard for approvals.

    Text arrives in fragments, so the terminal remembers whether a model line
    is open and closes it before printing anything else.
    """

    def __init__(self):
        self.text_open = False

    def emit(self, event: dict) -> None:
        kind = event["type"]
        if kind == "text":
            if not self.text_open:
                print("\n🤖 model › ", end="", flush=True)
                self.text_open = True
            print(event["text"], end="", flush=True)
            return

        if self.text_open:
            print()
            self.text_open = False

        if kind == "model_started":
            print(f"\n[model call {event['model_call']} started]", flush=True)
        elif kind == "tool":
            print(f"\ntool › {event['name']}({event['arguments']})")
        elif kind == "tool_result":
            print(f"tool ‹ {display_tool_result(event['output'])}")
        elif kind == "done":
            print(
                f"    [{event['model_calls']} model call(s) · {event['tool_calls']} tool call(s) · "
                f"{event['input_tokens']} in + {event['output_tokens']} out]\n"
            )

    def approve(self, command: str) -> bool:
        """Show the exact command. Empty or unrecognized input means no."""
        try:
            answer = input(
                f"\n[approval required]\n"
                f"Command: {command}\n"
                "Run it? Type yes to continue [y/N]: "
            )
        except (EOFError, KeyboardInterrupt):
            return False
        return answer.strip().lower() in {"y", "yes"}


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")
    headless = os.getenv("LEVEL8_HEADLESS", "").lower() in {"1", "true", "yes"}

    if "--new" in sys.argv:
        chat_file_path = history.new_chat()
    else:
        chat_file_path = history.latest_chat() or history.new_chat()

    terminal = Terminal()
    agent = Agent(
        OpenAI(),
        browser_tools.Browser(headless=headless),
        chat_file_path,
        emit=terminal.emit,
        approve=terminal.approve,
    )
    input_items = history.get_input_items(chat_file_path)
    print(f"[{chat_file_path.name} · {len(input_items)} input items so far]")
    print("[workspace: series-1-agent-class/08-persistence/agent_workspace]")
    print("Ctrl-D to leave. Ctrl-C interrupts the active turn.\n")

    try:
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
                print("\n[turn interrupted]")
                break
            except Exception as error:
                print(f"call failed: {error}", file=sys.stderr)
    finally:
        agent.close()


if __name__ == "__main__":
    main()
